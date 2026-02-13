import datetime
import pickle
class Post:
    def __init__(self, id, author, title, content, section, time=None):
        self.id = id  # 帖子唯一ID
        self.author = author  # 作者用户名或User对象
        self.title = title
        self.content = content
        self.section = section  # 板块名
        self.time = time if time else datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.comments = []  # 评论列表

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
        self.id = id  # 评论唯一ID
        self.post_id = post_id  # 所属帖子ID
        self.author = author  # 作者用户名或User对象
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
        try:
            with open(filename, 'wb') as f:
                pickle.dump(self.post_list, f)
        except Exception as e:
            print(f"Error saving posts: {e}")
    def load_posts(self, filename):
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