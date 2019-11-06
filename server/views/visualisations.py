import pandas as pd
import plotly.graph_objs as go
import plotly.offline as po
import pymongo
from flask import Blueprint, render_template, request

blueprint = Blueprint('visualisations', __name__)

config = {'DB_HOST': "mongodb://localhost:27017/",
          'DB_NAME': "behaworks_logger_v5",
          'DB_PORT': "",
          'URL_PREFIX': "/api"}

mongo = pymongo.MongoClient(config["DB_HOST"], )
db = mongo[config["DB_NAME"]]
movement_collection = db["test_movement"]


def get_user_ids():
    return movement_collection.distinct("user_id")


def get_session_ids(user_id=None):
    if user_id is not None:
        return movement_collection.distinct("session_id", {"user_id": user_id})
    else:
        return movement_collection.distinct("session_id")


def create_plot(query):
    df = pd.DataFrame(list(movement_collection.find(query)))
    splot_anim = [go.Scatter3d(
        x=df['x'],
        y=df['y'],
        z=df['z'],
        mode="lines",
        line=dict(width=2, color="blue"),
        opacity=0.1
    ), go.Scatter3d(
        x=df['x'],
        y=df['y'],
        z=df['z'],
        mode="lines",
        line=dict(width=2, color="blue"),
        opacity=0.1
    )]
    frames = [go.Frame(
        data=go.Scatter3d(
            x=df['x'][:k],
            y=df['y'][:k],
            z=df['z'][:k],
            mode='markers',
            marker=dict(
                color='rgb(255, 0, 0)',
                size=1,
                symbol='circle',
                line=dict(
                    color='rgb(255, 0, 0)',
                    width=1
                )
            ),

            opacity=0.1
        )
    ) for k in range(len(df['timestamp']))]

    layout_anim = go.Layout(
        width=1024,
        height=1024,
        scene=dict(
            camera=dict(up=dict(x=0, y=1, z=0)),
            xaxis=dict(title='X', range=[-2, 2]),
            yaxis=dict(title='Vyska', range=[-2, 2]),
            zaxis=dict(title='Z', range=[-2, 2])),
        updatemenus=[dict(type="buttons",
                          buttons=[dict(label="Play",
                                        method="animate",
                                        args=[None])])]
    )

    fig_anim = go.Figure(data=splot_anim, layout=layout_anim, frames=frames)
    frame_duration = df['timestamp'].tolist()[-1] / len(df['timestamp'])
    output = po.plot(fig_anim, output_type='div', animation_opts=dict(frame=dict(duration=frame_duration)))
    # graphJSON = json.dumps(output, cls=plotly.utils.PlotlyJSONEncoder)
    return output


@blueprint.route('/')
def root():
    user_id = None
    session_id = None

    try:
        user_id = request.args['user_id']
    except KeyError:
        pass
    try:
        session_id = request.args['session_id']
    except KeyError:
        pass

    if user_id is not None:
        return render_template('user_sessions.html',
                               user_id=user_id,
                               session_ids=get_session_ids(user_id)
                               )
    if session_id is not None:
        return render_template('graph.html', graph_div=create_plot({"session_id": session_id}))

    return render_template('index.html', user_ids=get_user_ids())

# @blueprint.route('/<user_id>')
# def user_sessions(user_id):
#     pass
