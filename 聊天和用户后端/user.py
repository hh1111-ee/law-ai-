import pickle
import threading
import tempfile
import os
class user:
    def __init__(self, id, username, identity, password, location, role=None):
        self.id=id
        self.username = username
        self.identity = identity  # 身份类型，如业主、物业、律师
        self.password = password
        self.location = location
        self.role = role if role else identity
        self.friends = []
        self.state="offline"
    def add_friend(self, friend):
        if friend not in self.friends:
            self.friends.append(friend)
        else:
            print("Friend already in the list.")
    def get_profile(self):
        return {
            "id": self.id,
            "username": self.username,
            "identity": self.identity,
            "role": self.role,
            "location": self.location,
            "state": self.state
        }
    def set_location(self, location):
        self.location = location
    def get_friends(self):
        return self.friends
    def set_state(self, state):
        self.state=state
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "identity": self.identity,
            "role": self.role,
            "location": self.location,
            "state": self.state,
            "friends": self.friends
        }
class userManage:
    def __init__(self):
        self.user_list = []
        self.lock = threading.Lock()
    def add_user(self, user):
        self.user_list.append(user)
    def remove_user(self, user):
        if user in self.user_list:
            self.user_list.remove(user)
        else:
            print("User not found in the list.")
    def find_user(self, username):
        for user in self.user_list:
            if user.username == username:
                return user
        return None
    def save_users(self, filename):
        with self.lock:
            fd = None
            tmp_path = None
            try:
                dirn = os.path.dirname(filename) or '.'
                fd, tmp_path = tempfile.mkstemp(dir=dirn)
                with os.fdopen(fd, 'wb') as f:
                    pickle.dump(self.user_list, f)
                os.replace(tmp_path, filename)
            except Exception as e:
                print(f"Error saving users: {e}")
                try:
                    if tmp_path and os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
    def load_users(self, filename):
        with self.lock:
            try:
                with open(filename, 'rb') as f:
                    self.user_list = pickle.load(f)
            except Exception as e:
                print(f"Error loading users: {e}")