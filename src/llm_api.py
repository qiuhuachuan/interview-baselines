import os

from openai import OpenAI

deepseek_client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com")

def get_llm_content(messages, model='deepseek-v4-flash'):
    print(messages)
    """Return one non-streaming DeepSeek chat response."""
    if not os.environ.get('DEEPSEEK_API_KEY'):
        raise RuntimeError('未配置 DEEPSEEK_API_KEY')

    completion = deepseek_client.chat.completions.create(
        model=model,
        messages=messages,
        stream=False,
        extra_body={"thinking": {"type": "disabled"}}
    )
    content = completion.choices[0].message.content
    print(content)
    if not content:
        raise RuntimeError('模型返回了空内容')
    return content


if __name__ == "__main__":
    prompt = '''你是谁？'''
    print(get_llm_content([{"role": "user", "content": prompt}], 'deepseek-v4-flash'))
