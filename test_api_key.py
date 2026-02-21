#!/usr/bin/env python3
"""Test script to verify Zhipu AI API key configuration"""

import os
import sys
from dotenv import load_dotenv
import zhipuai

# Load environment variables
load_dotenv()

def test_api_key():
    """Test if the Zhipu AI API key is correctly configured"""
    api_key = os.getenv("ZHIPU_API_KEY")

    print("=" * 50)
    print("智谱 AI API Key 配置测试")
    print("=" * 50)

    # Check if API key exists
    if not api_key:
        print("错误: ZHIPU_API_KEY 环境变量未设置")
        print("请在 .env 文件中设置: ZHIPU_API_KEY=your_api_key")
        return False

    print(f"API Key 已加载: {api_key[:10]}...{api_key[-6:]}")
    print(f"API Key 长度: {len(api_key)} 字符")

    # Test API connection
    try:
        print("\n正在测试智谱 AI API 连接...")
        client = zhipuai.ZhipuAI(api_key=api_key)

        # Simple test call
        response = client.chat.completions.create(
            model="glm-4-plus",
            messages=[
                {"role": "user", "content": "你好"}
            ],
            max_tokens=10
        )

        print("✅ API 连接成功!")
        print(f"模型响应: {response.choices[0].message.content}")
        print(f"模型: {response.model}")
        print(f"使用 tokens: {response.usage.total_tokens}")

        return True

    except zhipuai.core._errors.APIReachLimitError as e:
        print(f"⚠️ API 限制错误: {e}")
        if "余额不足" in str(e):
            print("提示: API Key 有效，但账户余额不足，请充值后使用")
        return True  # API Key is valid, just no balance
    except zhipuai.core._errors.APIAuthenticationError as e:
        print(f"❌ 认证错误: {e}")
        print("提示: API Key 可能无效或已过期")
        return False
    except Exception as e:
        print(f"❌ 连接错误: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_api_key()
    print("=" * 50)
    if success:
        print("测试通过! API Key 配置正确。")
    else:
        print("测试失败! 请检查 API Key 配置。")
    print("=" * 50)
    sys.exit(0 if success else 1)
