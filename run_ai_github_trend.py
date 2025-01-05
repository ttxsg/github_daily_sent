import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai
import os
import re
import asyncio
from crawl4ai import AsyncWebCrawler
# 提取 GitHub URL 中的 owner 和 repo
def extract_owner_repo(url):
    match = re.match(r'https://github.com/([^/]+)/([^/]+)', url)
    if match:
        owner = match.group(1)
        repo = match.group(2)
        return owner, repo
    else:
        return None, None

# 获取 GitHub 仓库的 README 内容（纯文本）
def get_github_readme(url_input):
    # url = f"https://github.com/{owner}/{repo}/blob/main/README.md"  # 使用 raw 来获取原始 Markdown 文件
    # response = requests.get(url_input)
    response = requests.get(url, verify=False)
    if response.status_code == 200:
        return response.text  # 直接返回原始的 Markdown 内容
    else:
        return f"请求失败，状态码: {response.status_code}"

# 提取所有图片链接
def extract_image_links(readme_markdown):
    image_links = re.findall(r'!\[.*?\]\((https?://[^\)]+\.(?:png|jpg|jpeg|gif|svg))\)', readme_markdown)
    return image_links

# 压缩图片
def compress_image(img_data, quality=10):
    try:
        # 使用 PIL 打开图片数据
        image = Image.open(BytesIO(img_data))
        
        # 如果图片是调色板模式 (P)，则转换为 RGB 模式
        if image.mode == 'P':
            image = image.convert('RGB')
        
        # 创建一个 BytesIO 对象来保存压缩后的图片
        output = BytesIO()
        
        # 将图片保存为 JPEG 格式，并设置压缩质量
        image.save(output, format="JPEG", quality=quality)
        
        # 返回压缩后的图片二进制数据
        output.seek(0)
        print('压缩成功')
        return output.read()
    
    except Exception as e:
        print(f"图片压缩失败: {e}")
        return img_data  # 如果压缩失败，返回原始图像数据
# 获取仓库的默认分支
def get_default_branch(input_url):
    # 使用 GitHub API 获取仓库信息
    url = f"https://api.github.com/repos/{owner}/{repo}"
    response = requests.get(input_url)
    if response.status_code == 200:
        data = response.json()
        return data.get('default_branch', 'main')  # 如果没有返回默认分支，则使用 'main'
    else:
        raise Exception(f"无法获取仓库信息，状态码: {response.status_code}")

# 定义生成总结的异步函数
async def generate_summary(url: str):
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(url=url)

        # 假设 `result.markdown_v2.raw_markdown` 是你的原始markdown字符串
        raw_markdown = result.markdown_v2.raw_markdown

        # 正则表达式提取从第一个标题到“36氪经授权发布”之前的所有正文内容
        # text_content = re.findall(r'##?.*?([\s\S]+?)(?=36氪经授权发布)', raw_markdown)
        # text_content = re.findall(r'##?\s?.*?([\s\S]+?)(?=36氪经授权发布|原创出品|(?=##))', raw_markdown)
        text_content = re.findall(r'lines[\s\S]*?([\s\S]+?)(?=36氪经授权发布|原创出品|## Footer|\Z)', raw_markdown)
        print(text_content[:500])
        if text_content:
            body = "\n".join(text_content).strip()
        else:
            body = "未找到正文部分"

        # 通过 Google Gemini 模型生成总结
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            summary_response = model.generate_content(f"用中文总结下面的文章，如果有图片地址，一起保留给我: {body}")
            return summary_response.text
        except Exception as e:
            print(f"生成总结时出错: {e}")
            return "未能生成总结"
# 创建翻译器实例
translator = GoogleTranslator(source='en', target='zh-CN')

# 从环境变量中读取 API 密钥
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)
# 定义 URL
URL = "https://github.com/trending?since=daily"

# 发送 HTTP GET 请求
response = requests.get(URL)
# 确认请求成功
if response.status_code == 200:
    # 使用 BeautifulSoup 解析 HTML 页面
    soup = BeautifulSoup(response.text, 'html.parser')
    
    repositories = []

    # 找到所有class为'Box-row'的'article'标签，每个'article'代表一个仓库
    for article in soup.find_all('article', class_='Box-row'):
        # 获取仓库名称和链接（在'h2'中的'a'标签里）
        name_tag = article.find('h2', class_='h3 lh-condensed').find('a')
        repo_name = name_tag.get_text(strip=True)
        repo_url = f"https://github.com{name_tag['href']}"

        # 获取仓库描述（在'p'标签中）
        description_tag = article.find('p', class_=lambda x: x != 'f6 color-fg-muted mt-2')
        if description_tag:
            description = description_tag.get_text(strip=True)
            # 使用 deep_translator 进行翻译
            try:
                translated_description = translator.translate(description)
            except Exception as e:
                print(f"翻译失败: {e}")
                translated_description = description
        else:
            translated_description = "暂无描述"
        
        # 获取编程语言（在'span'元素中，具有'itemprop'属性）
        language_tag = article.find('span', itemprop='programmingLanguage')
        if language_tag:
            language = language_tag.get_text(strip=True)
        else:
            language = "未知语言"
        
        # 获取星标数（在'href'属性包含'stargazers'的'a'标签里）
        stars_tag = article.find('a', href=lambda x: x and 'stargazers' in x)
        if stars_tag:
            stars = stars_tag.get_text(strip=True).replace(',', '')
            stars = int(stars) if stars.isdigit() else 0
        else:
            stars = 0
        
        # 将仓库信息添加到列表中
        repositories.append({
            'repo_name': repo_name,
            'repo_url': repo_url,
            'description': translated_description,
            'language': language,
            'stars': stars
        })
    #构建邮件内容
    email_content = ""
    # 根据星标数对列表进行排序（降序）
    sorted_repositories = sorted(repositories, key=lambda x: x['stars'], reverse=True)
    
    #  response = requests.get(url, verify=False)

    for repo in sorted_repositories:
        email_content += f'##📦 项目名称: {repo["repo_name"]}\n'
        email_content += f'🔗 地址: {repo["repo_url"]}\n'
        email_content += f'📝 描述: {repo["description"]}\n'
        email_content += f'💻 使用的语言: {repo["language"]}\n'
        email_content += f'⭐ 本周的收藏量: {repo["stars"]}\n'

        owner, repop = extract_owner_repo(repo["repo_url"])
        
            
        # readme_url = f"https://github.com/{owner}/{repo}/blob/{default_branch}/README.md"
        if owner and repop:
            default_branch = get_default_branch(repo["repo_url"])
            print(f"提取到的 owner: {owner}, repo: {repop}")
            # readme_content = get_github_readme(owner, repop)
            url = f'{repo["repo_url"]}/blob/{default_branch}/README.md'  # 使用 raw 来获取原始 Markdown 文件

            print(url)
            # 调用异步函数生成总结
            summary = asyncio.run(generate_summary(url))
        
            # if readme_content:
              
            #     image_links = extract_image_links(readme_content)
            # else:
            #     print("未找到 README 内容")
        else:
            summary="无法从 URL 中提取 "
            print("无法从 URL 中提取 owner 和 repo")
         # 通过 Google Gemini 模型生成总结
         
          
        email_content += f'⭐ README 内容: {summary}\n'
        # email_content += f'⭐ 图片地址: {image_links}\n'
        email_content += '\n'
        

    # 邮件发送配置
    sender_email = "386857251@qq.com"  # 使用环境变量
    sender_password = "qosozmmhfzyybhgi"  # 使用环境变量
    recipient_email = "zhengxinlilili@gmail.com"  # 使用环境变量

    # 创建邮件对象
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = "每日 GitHub Trending 仓库"

    # 附加文本内容
    message.attach(MIMEText(email_content, "plain", "utf-8"))

    try:
        # 连接到 QQ 邮箱的 SMTP 服务器
        with smtplib.SMTP("smtp.qq.com", 587) as server:
            server.starttls()  # 启用加密传输
            server.login(sender_email, sender_password)  # 登录
            server.sendmail(sender_email, recipient_email, message.as_string())  # 发送邮件

        print("邮件发送成功！")
    except Exception as e:
        print(f"邮件发送失败: {e}")

else:
    print("获取页面失败")
