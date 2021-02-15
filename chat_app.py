from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_socketio import SocketIO, join_room, leave_room
from models import Database
from collections import defaultdict, OrderedDict
import secrets
import os
import random
import string

app = Flask(__name__)
app.secret_key = secrets.token_urlsafe(32)
socketio =SocketIO(app,async_mode="threading",logger=True, engineio_logger=True)
sessions = OrderedDict()
clients = []
files = defaultdict(lambda:bytearray(0), {})

FILE_UPLOAD_LIMIT = 2.5*10**7

# @app.route('/')
# def nav():
#     return render_template("template.html")

def messageReceived(methods=['GET','POST']):
    print("Message received")

@socketio.on('connect')
def handle_user_connect():
    socketio.emit("user_connected",{"id":request.sid},callback=messageReceived,room=request.sid)

@socketio.on('disconnect')
def handle_user_disconnect():

    client = request.sid

    print("sid: " + client)

    room=sessions[client]
    try:
        del sessions[client]
    except KeyError:
        print(f"Failed to delete id {client}")

    room_total = sum(map((room).__eq__, sessions.values()))
    leave_room(room)

    if room_total > 0:
        socketio.emit("room_status", {'room_status': room_total}, room=room)
    else:
        id = room.split("-")[-1]
        DATABASE = Database("chatroom_app")
        DATABASE.openDatabase()
        DATABASE.closeRoom(room_id=id)


@socketio.on('user_send_message')
def handle_user_message(json):
    if (len(json['message'])>0):
        json['message'] = json['message'].replace("\n","<br/>")
        json['sessionId'] = request.sid
        socketio.emit("approve_message",json,callback=messageReceived,room=json["room_name"])


@socketio.on("request_upload")
def request_upload(json):
    if json['size'] < FILE_UPLOAD_LIMIT:
       print(json)
       socketio.emit("approve_upload",json,room=request.sid)


@socketio.on("slice_upload")
def user_file_upload(json):

    files[request.sid] += json['data']

    if len(files[request.sid]) == int(json['size']):

        mypath = "C:\\Users\\gregf\\OneDrive\\Documents\\Python Projects\\chat_app\\files"

        if not os.path.exists(mypath):
            os.makedirs(mypath)

        fname = mypath + "\\" + json['name']

        with open(fname,"wb") as f:
            f.write(files[request.sid])


        DATABASE = Database("chatroom_app")
        DATABASE.openDatabase()
        DATABASE.createTable('files')
        url = DATABASE.insertFile(fname, int(json['size']))

        socketio.emit("finished_upload",{"user":json['user'],"message": json["message"],"url":url, "sessionId" : request.sid},room=sessions[request.sid])

        del files[request.sid]


@socketio.on("cancel_upload")
def cancel_upload():
    files.pop(request.sid, None)


@socketio.on("join")
def on_join(data):

    def randomString(stringLength=5):
        lettersAndDigits = string.ascii_letters + string.digits
        return ''.join((random.choice(lettersAndDigits) for i in range(stringLength)))

    id = data["id"]
    name = data["name"]
    room = f"{name}-{id}"

    DATABASE = Database("chatroom_app")
    DATABASE.openDatabase()
    roomdetails = DATABASE.selectRoom(room_id=id)

    client = request.sid

    join = sum(map((room).__eq__, sessions.values())) < roomdetails[1]
    if join:
        join_room(room)
        sessions[client] = room
        socketio.emit("join",{"username":f"user-{randomString(5)}","sessionId":client},room=client)
        socketio.emit("room_status", {'room_status': sum(map((room).__eq__, sessions.values())), "join_status": str(join).lower()}, room=room)
    else:
        print(f"room {name} full.")


@app.route('/')
def home():
    return render_template("home.html")


@app.route("/error")
def error(msg):
    return render_template("error.html",error_message=msg)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/chat")
def chat():
    error = ""
    if session.get("error"):
        error = session.get("error")

    session['error'] = ""
    return render_template("create-session.html",error_message=error)


@app.route("/download/<url>")
def download_file(url):
    DATABASE = Database("chatroom_app")
    DATABASE.openDatabase()
    path = DATABASE.selectFile(url=url)

    if path is None:
        return render_template("error.html",error_message="The file you are looking for has expired or does not exist.")

    return send_file(path[0], as_attachment=True)


@app.route("/chat/<string:name>/<string:id>")
def load_session(name,id):
    DATABASE = Database("chatroom_app")
    DATABASE.openDatabase()
    roomdetails = DATABASE.selectRoom(room_id=id)

    room = f"{name.replace('_',' ')}-{id}"

    if roomdetails is not None and roomdetails[2] is None and roomdetails[0] == name:
        if sum(map((room).__eq__, sessions.values())) < roomdetails[1]:
            return render_template("session.html", chatroom_name=name.replace("_", " "),chatroom_id = id,chatroom_amount=roomdetails[1])
        else:
            error_message = f"{name} is full"
    else:
        error_message = f"{name} does not exist or has been closed."

    session["error"] = error_message

    return redirect(url_for("chat"))


@app.route("/chat",methods=['POST'])
def create_session():

    if request.form:
        chatroom_amount = request.form['amount']
        chatroom_name = request.form['name'].strip()

        chatroom_name = " ".join(chatroom_name.split())
        chatroom_name = chatroom_name.replace(" ", "_")

        DATABASE = Database("chatroom_app")
        DATABASE.openDatabase()
        DATABASE.createTable("chatroom")
        chatroom_id = DATABASE.insertRoom(chatroom_name, chatroom_amount)
        return redirect(url_for(".load_session",name=chatroom_name, id=chatroom_id))

    # return render_template("error.html")

if __name__ == '__main__':
    DATABASE = Database("chatroom_app")
    DATABASE.openDatabase()
    DATABASE.createTable("chatroom")
    DATABASE.createTable("files")
    app.run(debug=True,port=5000)

