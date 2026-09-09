"""运行时与存储入口。router / service 经此取依赖。"""
from api import state


def runtime():
    return state.runtime


def conversation_store():
    return state.conversation_store
