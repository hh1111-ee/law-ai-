from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from .db_session import Base


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, index=True, nullable=False)
    # 保持与旧模型兼容：保留明文密码列（旧系统使用），同时新增 password_hash
    # 迁移后可以移除 `password` 列并仅使用 `password_hash`
    password = Column(String(128), nullable=True)
    password_hash = Column(String(256), nullable=True)
    # 兼容旧字段
    identity = Column(String(64), nullable=True)
    # 额外字段以兼容历史数据
    location = Column(String(128), nullable=True)
    # 规范化地区字段已移除（数据库中无 regions 表时保留向后兼容）
    # 好友列表短期以 JSON 存储用户名列表，便于保留原数据结构并后续迁移
    friends = Column(JSON, nullable=True)
    role = Column(String(32), default='user')
    state = Column(String(32), default='active')
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Post(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    # 保留板块字段以兼容旧 Post 的 `section`
    section = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Comment(Base):
    __tablename__ = 'comments'
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey('posts.id'), nullable=False)
    author_name = Column(String(80), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    # groupmaster 可以暂存为 user id
    groupmaster_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    # 成员短期以 JSON 存储用户名或 id 列表，便于迁移
    members = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Case(Base):
    __tablename__ = 'cases'
    id = Column(Integer, primary_key=True, index=True)
    case_number = Column(String(128), unique=True, index=True)
    summary = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)  # 可存 JSON 或逗号分隔关键词
    # 可关联 region
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExampleLegal(Base):
    """用于存放法规/条例等条目，来源于 `数据/地区.xlsx` 的行。

    列示例：地区, 网页链接, 法规名称
    """
    __tablename__ = 'example_legal'
    id = Column(Integer, primary_key=True, index=True)
    region = Column(String(128), nullable=True, index=True)
    url = Column(String(1024), nullable=True)
    title = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExampleRelation(Base):
    """用于存放案号类表（真实案件/裁判要旨），对应 `数据/案号.xlsx`。

    列示例：案号, 链接, 摘要, 关键词1, 关键词2, 关键词3
    """
    __tablename__ = 'example_relation'
    id = Column(Integer, primary_key=True, index=True)
    case_number = Column(String(256), unique=True, index=True, nullable=False)
    url = Column(String(1024), nullable=True)
    summary = Column(Text, nullable=True)
    keyword1 = Column(String(128), nullable=True)
    keyword2 = Column(String(128), nullable=True)
    keyword3 = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PersonalMessage(Base):
    __tablename__ = 'personal_messages'
    id = Column(Integer, primary_key=True, index=True)
    sender = Column(Integer, nullable=False)
    receiver = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GroupMessage(Base):
    __tablename__ = 'group_messages'
    id = Column(Integer, primary_key=True, index=True)
    group_name = Column(String(128), nullable=False)
    sender = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
