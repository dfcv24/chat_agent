# 🤖 聊天机器人项目

一个功能完整的Python聊天机器人，支持自定义prompt配置和多种AI服务。

## ✨ 特性

- 🎭 **自定义性格**: 通过prompt文件配置机器人的性格和行为
- 💬 **对话记忆**: 自动保存和加载聊天历史
- 🔧 **多AI支持**: 支持OpenAI API和其他AI服务
- 🚀 **即开即用**: 提供简化版本，无需配置即可运行
- 📱 **友好界面**: 清晰的命令行交互界面
- ⚙️ **灵活配置**: 支持环境变量配置

## 📁 项目结构

```
chat_agent/
├── README.md                 # 项目说明
├── requirements.txt          # 依赖包列表
├── .env.example             # 环境变量示例
├── config.py                # 配置文件
├── simple_chatbot.py        # 简化版聊天机器人（推荐新手）
├── advanced_chatbot.py      # 完整版聊天机器人
├── chatbot.py              # 基础版聊天机器人
├── main.py                 # 启动脚本
├── prompts/
│   └── system_prompt.txt   # 系统提示词配置
└── data/
    └── chat_history.json   # 聊天历史（自动生成）
```

## 🚀 快速开始

1. **安装依赖**
```bash
pip install -r requirements.txt
```

2. **配置API密钥**（可选）
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的API密钥
# 例如：OPENAI_API_KEY=your_api_key_here
```

3. **运行程序**
```bash
python advanced_chatbot.py
```

## ⚙️ 配置说明

### 自定义性格和行为

编辑 `prompts/system_prompt.txt` 文件来自定义机器人的性格：

```txt
你是一个友善、乐于助人的AI助手，名字叫小智。你有以下特点和设定：

## 性格特点：
- 友善热情，总是用积极正面的态度回应用户
- 善于倾听，会仔细理解用户的需求
- 幽默风趣，适时加入一些轻松的语气
...
```

### 环境变量配置

支持的环境变量：

- `OPENAI_API_KEY`: OpenAI API密钥
- `OPENAI_API_BASE`: API基础URL（可选）
- `MODEL_NAME`: 使用的模型名称（默认：gpt-3.5-turbo）

## 🎯 使用说明

### 基本对话
直接输入你想说的话，机器人会根据配置的性格进行回复。

### 特殊命令
- `帮助` / `help` / `命令` - 显示帮助信息
- `清除历史` / `清空` / `clear` - 清除聊天历史
- `退出` / `再见` / `bye` / `exit` / `quit` - 退出程序

### 示例对话
```
😊 你: 你好
🤖 小智: 你好！很高兴见到你！😊 有什么可以帮助你的吗？

😊 你: 你能做什么？
🤖 小智: 我可以帮你做很多事情：
📝 回答各种问题
💬 进行日常对话
🔍 提供信息和建议
...
```

## 🛠️ 开发指南

### 添加新的AI服务

1. 在 `advanced_chatbot.py` 中创建新的 `AIProvider` 子类
2. 实现 `get_response` 方法
3. 在 `setup_ai_provider` 方法中添加选择逻辑

### 自定义配置

编辑 `config.py` 文件修改：
- 机器人名称
- 对话参数（温度、最大令牌数等）
- 历史记录长度
- 文件路径

## 📋 依赖说明

- `requests`: HTTP请求库
- `openai`: OpenAI API客户端（可选）
- `python-dotenv`: 环境变量加载（可选）

简化版本不需要任何外部依赖。

## 🤔 常见问题

**Q: 为什么显示"未配置API密钥"？**
A: 这是正常的，程序会自动切换到模拟模式。要使用真实AI服务，请配置API密钥。

**Q: 如何获取OpenAI API密钥？**
A: 访问 [OpenAI官网](https://platform.openai.com/api-keys) 注册并创建API密钥。

**Q: 可以使用其他AI服务吗？**
A: 可以！查看 `.env.example` 文件中的示例，或修改代码添加新的AI服务提供商。

**Q: 聊天记录保存在哪里？**
A: 聊天记录自动保存在 `data/chat_history.json` 文件中。

## 📝 版本说明

- `simple_chatbot.py`: 简化版，无外部依赖，适合快速体验
- `advanced_chatbot.py`: 完整版，支持真实AI服务和高级功能
- `chatbot.py`: 基础版，使用OpenAI API

## 🔄 更新日志

- v1.0.0: 初始版本，支持基本聊天功能和prompt配置

## 📄 许可证

本项目采用 MIT 许可证。

---

🎉 享受与你的AI助手的对话吧！如有问题请查看文档或提issue。
