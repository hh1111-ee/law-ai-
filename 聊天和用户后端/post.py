import datetime
import pickle
import threading
import tempfile
import os

class Post:
    def __init__(self, id, author, title, content, section, time=None):
        self.id = id
        self.author = author
        self.title = title
        self.content = content
        self.section = section
        self.time = time if time else datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.comments = []

    def add_comment(self, comment):
        self.comments.append(comment)

    def to_dict(self):
        return {
            'id': self.id,
            'author': self.author,
            'title': self.title,
            'content': self.content,
            'section': self.section,
            'time': self.time,
            'comments': [c.to_dict() for c in self.comments]
        }


class Comment:
    def __init__(self, id, post_id, author, content, time=None):
        self.id = id
        self.post_id = post_id
        self.author = author
        self.content = content
        self.time = time if time else datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def to_dict(self):
        return {
            'id': self.id,
            'post_id': self.post_id,
            'author': self.author,
            'content': self.content,
            'time': self.time
        }


class PostManage:
    def __init__(self):
        self.post_list = []
        self.next_post_id = 1
        self.next_comment_id = 1
        self.thread_lock = threading.Lock()
    def add_post(self, author, title, content, section):
        post = Post(self.next_post_id, author, title, content, section)
        self.post_list.append(post)
        self.next_post_id += 1
        return post

    def get_post(self, post_id):
        for post in self.post_list:
            if post.id == post_id:
                return post
        return None

    def add_comment(self, post_id, author, content):
        post = self.get_post(post_id)
        if post:
            comment = Comment(self.next_comment_id, post_id, author, content)
            post.add_comment(comment)
            self.next_comment_id += 1
            return comment
        return None

    def get_posts(self, section=None):
        if section:
            return [p for p in self.post_list if p.section == section]
        return self.post_list

    def to_dict(self):
        return [p.to_dict() for p in self.post_list]

    def save_posts(self, filename):
        with self.thread_lock:
            try:
                dir_name = os.path.dirname(filename) or '.'
                fd, tmp_path = tempfile.mkstemp(dir=dir_name)
                try:
                    with os.fdopen(fd, 'wb') as f:
                        pickle.dump(self.post_list, f)
                    os.replace(tmp_path, filename)
                except Exception:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    raise
            except Exception as e:
                print(f"Error saving posts: {e}")

    def load_posts(self, filename):
        with self.thread_lock:
            try:
                with open(filename, 'rb') as f:
                    self.post_list = pickle.load(f)
                    if self.post_list:
                        self.next_post_id = max(p.id for p in self.post_list) + 1
                        all_comments = [c for p in self.post_list for c in p.comments]
                        if all_comments:
                            self.next_comment_id = max(c.id for c in all_comments) + 1
            except Exception as e:
                print(f"Error loading posts: {e}")
