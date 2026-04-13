from db import users

def login(username, password):
    user = users.find_one({"username": username, "password": password})
    return user

def register(username, password):
    users.insert_one({
        "username": username,
        "password": password,
        "role": "student"
    })