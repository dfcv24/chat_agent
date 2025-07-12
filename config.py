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
    API_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    MEMORY_MODEL_NAME = os.getenv("MEMORY_MODEL", "gpt-3.5-turbo")
    CHAT_MODEL_NAME = os.getenv("CHAT_MODEL", "gpt-3.5-turbo")  # 用于对话的模型
    CODE_MODEL_NAME = os.getenv("CODE_MODEL", "gpt-3.5-turbo")  # 用于代码生成的模型
    THINK_MODEL_NAME = os.getenv("THINK_MODEL", "gpt-3.5-turbo")  # 用于思考的模型
    
    # 对话设置
    MAX_TOKENS = 2000
    TEMPERATURE = 0.9
    TOP_P = 0.9  # Top-p采样
    MAX_HISTORY_LENGTH = 10  # 保留的对话历史条数
    
    # 文件路径
    PROMPT_FILE = "prompts/system_prompt.txt"
    CHAT_HISTORY_FILE = "data/chat_history.json"
    USER_KNOWLEDGE_FILE = "data/user_knowledge.json"
    KNOWLEDGE_TEMPLATE_FILE = "data/user_knowledge_template.json"
    
    # 界面设置
    WELCOME_MESSAGE = f"嗨～我是{BOT_NAME}啦，今天可以陪你聊天哦～你不会嫌我烦吧？🥺"
    
    # 特殊命令
    EXIT_COMMANDS = ["退出", "再见", "bye", "exit", "quit"]
    CLEAR_COMMANDS = ["清除历史", "清空", "clear"]
    HELP_COMMANDS = ["帮助", "help", "命令"]
    
    # 知识管理设置
    ENABLE_KNOWLEDGE_LEARNING = True  # 是否启用知识学习
    AUTO_ASK_QUESTIONS = True  # 是否自动询问用户信息
    QUESTION_PROBABILITY = 0.3  # 主动询问问题的概率（0-1）
    
    # 异步交互设置
    PROACTIVE_QUESTION_DELAY = 5  # 用户空闲多少秒后开始主动提问
    MAX_IDLE_TIME = 60  # 用户最大空闲时间（秒），超过后不再主动提问
    QUESTION_CHECK_INTERVAL = 10  # 检查是否需要主动提问的间隔（秒）
    
    # 向量数据库设置
    MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
    MILVUS_COLLECTION_NAME = os.getenv("MILVUS_COLLECTION_NAME", "chat_agent_test")
    
    # Embedding设置 - 使用硅基流动的embedding API
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")  # 硅基流动支持的embedding模型
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))  # bge-m3的嵌入维度是1024
    # 或者qwen-embedding-8b，先用bge-m3，后续可以切换到qwen-embedding-8b
    
    # 向量搜索设置
    VECTOR_SEARCH_LIMIT = int(os.getenv("VECTOR_SEARCH_LIMIT", "5"))
    SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
