import argparse
import time
from itertools import combinations, repeat
from multiprocessing import Pool
from random import shuffle

import pandas as pd
import scipy.special
import tqdm
from sklearn.model_selection import train_test_split

from server.config import config
from server.db import create_db
from server.db.test_mongo import TestMongo
from server.lookup.faiss import TestModel
from utils.helpers import append_score

UNKNOWN_USERS_RATIO = 0.3


def cv_run(arguments):
    unknown_users, df_all, selected_features, model = arguments
    df_unknown = df_all.loc[df_all['user_id'].isin(unknown_users)]
    df_known = df_all.loc[~df_all['user_id'].isin(unknown_users)]
    train, test = train_test_split(df_known, stratify=df_known['user_id'])
    test = test.append(df_unknown)
    model.fit(train[selected_features])
    return model.evaluate(test[selected_features], verbose)[0]


def cross_validation(df_all, model=TestModel(), selected_features=None, processes=1):
    user_ids = df_all['user_id'].unique()
    if selected_features is None or len(selected_features) == 0:
        selected_features = list(df_all.columns)
    shuffle(user_ids)
    scores = None
    pool = Pool(processes)
    for score in tqdm.tqdm(
            pool.imap_unordered(cv_run, zip(combinations(user_ids, max(1, int(len(user_ids) * UNKNOWN_USERS_RATIO))),
                                            repeat(df_all),
                                            repeat(selected_features),
                                            repeat(model))),
            total=scipy.special.comb(len(user_ids), max(1, int(len(user_ids) * UNKNOWN_USERS_RATIO))), ascii=True):
        scores = append_score(scores, score)
    pool.close()
    pool.join()
    return scores


def evaluation(features=None, quick=False, iterations=1, threshold=config.MAXIMAL_DISTANCE,
               neighbours=config.NEIGHBOURS, processes=1):
    db = create_db(TestMongo())
    df, df_test = db.get_clean_train_test()
    if features is not None:
        features = config.FEATURE_SELECTION[features] + ['user_id']

    if quick:
        m = TestModel()
        m.fit(df[features])
        m.evaluate(df_test[features], True)
    else:
        df = df.append(df_test)
        user_ids = df['user_id'].unique()
        shuffle(user_ids)
        final_list = []

        print(user_ids)

        for i in range(2, 11):
            score_df = None
            for j in range(len(user_ids) - (i - 1)):
                to_use_user_ids = user_ids[j:j + i]
                print(to_use_user_ids)
                for _ in tqdm.tqdm(range(iterations), ascii=True):
                    run_scores = cross_validation(df[df['user_id'].isin(to_use_user_ids)],
                                                  model=TestModel(maximal_distance=threshold, neighbours=neighbours),
                                                  selected_features=features, processes=processes)

                    if score_df is not None:
                        score_df = score_df.append(run_scores)
                    else:
                        score_df = run_scores.copy()
            if len(final_list) == 0:
                final_list.append(["k-users"] + list(score_df.columns))

            final_list.append([i] + list(score_df.mean().values))
            print(str(i) + ":\n" + str(score_df.mean().rename('Mean')))
    print(final_list)
    final_df = pd.DataFrame(final_list[1:], columns=final_list[0])
    print(final_df)
    return final_df


args = None
verbose = False
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run model cross-validation.")
    parser.add_argument('-p', '--processes', type=int, help='Number of processes (default: %(default)s)', default=1)
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-q', '--quick', action='store_true',
                        help="Don't run cross-validation, just evaluate the model once")
    parser.add_argument('--no_save', action='store_true', help="Don't save cross-validation results")
    parser.add_argument('-i', '--iterations', type=int,
                        help='How many times to run the validation (default: %(default)s)',
                        default=1)
    parser.add_argument('-n', '--neighbours', type=int, help='K for KNN (default: %(default)s)',
                        default=config.NEIGHBOURS)
    parser.add_argument('-t', '--threshold', type=int,
                        help='Threshold for marking user as a new user (default: %(default)s)',
                        default=config.MAXIMAL_DISTANCE)
    parser.add_argument('-f', '--features', type=int, help='Feature set to use (default: use all features)',
                        choices=range(len(config.FEATURE_SELECTION)))

    args = parser.parse_args()

    verbose = args.verbose

    s_df = evaluation(features=args.features, quick=args.quick, iterations=args.iterations, threshold=args.threshold,
                      neighbours=args.neighbours, processes=args.processes)

    if not args.no_save:
        s_df.to_csv(
            rf'cv_evaluation_f-{args.features}_n-{args.neighbours}_t-{args.threshold}_{time.strftime("%Y%m%d-%H%M%S")}.csv',
            index=False)
    print(s_df.mean().rename('Mean'))
