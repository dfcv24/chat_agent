# 聊天机器人配置文件
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class ChatConfig:
    # 基本设置
    BOT_NAME = "银月"
    VERSION = "1.0.0"
    
    # API设置 (这里以OpenAI为例，你可以根据需要修改)
    # 请在环境变量中设置你的API密钥
    API_KEY = os.getenv("OPENAI_API_KEY")
    API_BASE_URL = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    MODEL_NAME = os.getenv("MEMORY_MODEL", "gpt-3.5-turbo")
    
    # 对话设置
    MAX_TOKENS = 2000
    TEMPERATURE = 0.9
    TOP_P = 0.9  # Top-p采样
    MAX_HISTORY_LENGTH = 10  # 保留的对话历史条数
    
    # 文件路径
    PROMPT_FILE = "prompts/system_prompt.txt"
    CHAT_HISTORY_FILE = "data/chat_history.json"
    
    # 界面设置
    WELCOME_MESSAGE = f"嗨～我是{BOT_NAME}啦，今天可以陪你聊天哦～你不会嫌我烦吧？🥺"
    
    # 特殊命令
    EXIT_COMMANDS = ["退出", "再见", "bye", "exit", "quit"]
    CLEAR_COMMANDS = ["清除历史", "清空", "clear"]
    HELP_COMMANDS = ["帮助", "help", "命令"]
