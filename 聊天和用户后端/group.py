from user import user
import pickle
class group:
    def __init__(self, name,groupmaster, users=None):
        self.name = name
        self.groupmaster = groupmaster
        self.users = users if users is not None else []
    def add_member(self, user):
        self.users.append(user)
    def remove_member(self, user):
        if user in self.users:
            self.users.remove(user)
        else:
            print("User not found in the group.")
class groupManage:
    def __init__(self):
        self.group_list = []
    def add_group(self, group):
        self.group_list.append(group)
    def remove_group(self, group):
        if group in self.group_list:
            self.group_list.remove(group)
        else:
            print("Group not found in the list.")
    def find_group(self,name):
        for group in self.group_list:
            if group.name==name:
                return group
        return None
    def save_groups(self, filename):
        try:
            with open(filename, 'wb') as f:
                pickle.dump(self.group_list, f)
        except Exception as e:
            print(f"Error saving groups: {e}")
    def load_groups(self, filename):
        try:
            with open(filename, 'rb') as f:
                self.group_list = pickle.load(f)
        except Exception as e:
            print(f"Error loading groups: {e}")