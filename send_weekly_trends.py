
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 创建翻译器实例
translator = GoogleTranslator(source='en', target='zh-CN')

# 定义 URL
URL = "https://github.com/trending?since=weekly"

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
    
    # 根据星标数对列表进行排序（降序）
    sorted_repositories = sorted(repositories, key=lambda x: x['stars'], reverse=True)
    
    # 构建邮件内容
    email_content = ""
    for repo in sorted_repositories:
        email_content += f'📦 项目名称: {repo["repo_name"]}\n'
        email_content += f'🔗 地址: {repo["repo_url"]}\n'
        email_content += f'📝 描述: {repo["description"]}\n'
        email_content += f'💻 使用的语言: {repo["language"]}\n'
        email_content += f'⭐ 本周的收藏量: {repo["stars"]}\n'
        email_content += '-' * 40 + '\n'

    # 邮件发送配置
    sender_email = "386857251@qq.com"  # 使用环境变量
    sender_password = "qosozmmhfzyybhgi"  # 使用环境变量
    recipient_email = "zhengxinlilili@gmail.com"  # 使用环境变量

    # 创建邮件对象
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = "每周 GitHub Trending 仓库"

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
