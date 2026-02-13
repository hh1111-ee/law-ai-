from group import group
from user import user
import pickle
class personalChatMessage:
    def __init__(self, sender, receiver, content, timestamp):
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.timestamp = timestamp

    def get_message_info(self):
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "timestamp": self.timestamp
        }

    def save_message(self, filename):
        with open(filename, 'wb') as f:
            pickle.dump(self.get_message_info(), f)
class groupChatMessage:
    def __init__(self, sender, group, content, timestamp):
        self.sender = sender
        self.group = group
        self.content = content
        self.timestamp = timestamp
    def get_message_info(self):
        return {
            "sender": self.sender,
            "group": self.group,
            "content": self.content,
            "timestamp": self.timestamp
        }   
    def save_message(self, filename):
        with open(filename, 'wb') as f:
            pickle.dump(self.get_message_info(), f)
class MessageManage:
    def __init__(self):
        self.personal_messages = []
        self.group_messages = []
    def add_personal_message(self, message):
        self.personal_messages.append(message)
    def get_personal_messages(self, user1, user2):
        # 自动将所有参与者转为字符串，避免类型不一致导致查不到消息
        def to_username(val):
            return getattr(val, 'username', str(val))
        u1 = str(user1)
        u2 = str(user2)
        result = []
        
        for msg in self.personal_messages:
            sender = to_username(msg.sender)
            receiver = to_username(msg.receiver)
            match = (sender == u1 and receiver == u2) or (sender == u2 and receiver == u1)
            if match:
                result.append(msg)
            
        return result
    def add_group_message(self, message):
        self.group_messages.append(message)
    def save_personal_messages(self, filename):
        try:
            with open(filename, 'wb') as f:
                pickle.dump(self.personal_messages, f)
        except Exception as e:
            print(f"Error saving personal messages: {e}")
    def load_personal_messages(self, filename):
        try:
            with open(filename, 'rb') as f:
                self.personal_messages = pickle.load(f)
        except Exception as e:
            print(f"Error loading personal messages: {e}")
    def save_group_messages(self, filename):
        try:
            with open(filename, 'wb') as f:
                pickle.dump(self.group_messages, f)
        except Exception as e:
            print(f"Error saving group messages: {e}")
    def load_group_messages(self, filename):
        try:
            with open(filename, 'rb') as f:
                self.group_messages = pickle.load(f)
        except Exception as e:
            print(f"Error loading group messages: {e}")
     
