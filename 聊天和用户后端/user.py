import pickle
class user:
    def __init__(self, username, identity, password, location, role=None):
        self.username = username
        self.identity = identity  # 身份类型，如业主、物业、律师
        self.password = password
        self.location = location
        self.role = role if role else identity
        self.friends = []
        self.state="office"
    def add_friend(self, friend):
        if friend not in self.friends:
            self.friends.append(friend)
        else:
            print("Friend already in the list.")
    def get_profile(self):
        return {
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
        try:
            with open(filename, 'wb') as f:
                pickle.dump(self.user_list, f)
        except Exception as e:
            print(f"Error saving users: {e}")
    def load_users(self, filename):
        try:
            with open(filename, 'rb') as f:
                self.user_list = pickle.load(f)
        except Exception as e:
            print(f"Error loading users: {e}")  
        
