import os
import re
import uuid
import smtplib
import imaplib
import email
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from enum import Enum 
from colorama import Fore, Style
from dotenv import load_dotenv
load_dotenv()

from src.utils.redis_utils import redis_conn
from .schema_mail import Email

class EmailStatus(Enum):
    UNPROCESSED = ("unprocessed", "新读取的邮件，未处理")
    AUTO_REPLIED = ("auto_replied", "已自动回复的邮件") 
    MANUAL_PENDING = ("manual_pending", "需人工处理，暂存待介入")
    MANUAL_REPLIED = ("manual_replied", "已人工处理并回复的邮件")
    IGNORED = ("ignored", "已忽略的邮件（如垃圾邮件）")

    @property
    def desc(self):
        """快速获取中文描述的方法"""
        return self.value[1]

    @property
    def status_value(self):
        """快速获取状态值（可选，避免记混元组顺序）"""
        return self.value[0]

class QQMailTools:
    def __init__(self):
        self.email_from = os.getenv("EMAIL_FROM")
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = os.getenv("SMTP_PORT")
        self.email_account = os.getenv("EMAIL_ACCOUNT")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.email_delay_hours = os.getenv("EMAIL_DELAY_HOURS")
        self.imap_host = os.getenv("IMAP_HOST")
        self.imap_port = os.getenv("IMAP_PORT")

        # 引入Redis
        self.redis_conn = redis_conn
    
    def fetch_unanswered_emails(self, max_results=20):
        """
        获取最近 N 小时内的未读且未处理
        """
        try:
            # 得到
            if not self.email_delay_hours or not self.email_delay_hours.isdigit():
                print(f"{Fore.YELLOW} EMAIL_DELAY_HOURS配置无效, 默认使用8小时{Style.RESET_ALL}")
                self.email_delay_hours = "8"

            now = datetime.now()
            time_limit = now - timedelta(hours=int(self.email_delay_hours))
            since_str = time_limit.strftime("%d-%b-%Y")

            # 建立IMAP连接
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.email_account, self.email_password)
            mail.select("inbox")

            # 搜索最近 N 小时内的未读邮件
            search_criteria = f'(UNSEEN SINCE "{since_str}")'
            status, data = mail.search(None, search_criteria)
            if status != "OK":
                print(f"{Fore.RED} 搜索邮件失败 {Style.RESET_ALL}")
                return []
            email_ids = data[0].split()

            unanswered_emails = []
            for eid in email_ids[:max_results]:
                eid_str = eid.decode()
                redis_key = self._get_redis_key(eid_str)
                # 判重逻辑：排除非「UNPROCESSED」状态的邮件
                if self.redis_conn and self.redis_conn.exists(redis_key):
                    existing_status = self.redis_conn.hget(redis_key, "status")
                    # 非未处理状态列表（包含其他4种状态）
                    non_unprocessed_status = [
                        EmailStatus.AUTO_REPLIED.status_value,
                        EmailStatus.MANUAL_PENDING.status_value,
                        EmailStatus.MANUAL_REPLIED.status_value,
                        EmailStatus.IGNORED.status_value
                    ]
                    if existing_status in non_unprocessed_status:
                        existing_desc = self.redis_conn.hget(redis_key, "status_desc")
                        print(f"⏭️  邮件{eid_str}已跳过 | 状态：{existing_desc}")
                        continue

                # 解析邮件
                status, msg_data = mail.fetch(eid, "(RFC822)")
                if status != "OK":
                    print(f"{Fore.RED}❌ 获取邮件{eid_str}失败{Style.RESET_ALL}")
                    continue
                msg = email.message_from_bytes(msg_data[0][1])

                # 解析主题（处理中文编码）
                subject, encoding = decode_header(msg.get("Subject", ""))[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="ignore")
                # 解析发件人、Message-ID、对话线程ID
                from_ = msg.get("From", "Unknown")
                message_id = msg.get("Message-ID", f"<{uuid.uuid4()}@qq.com>")
                thread_id = msg.get("In-Reply-To", message_id)
                # 解析正文
                body = self._get_email_body(msg)
                # 2解析 References 字段（从邮件头获取，对应 Email 类的 references 字段）
                references = msg.get("References", "")  # 若邮件头无References，默认空字符串
                references = references.strip()
                email_info = {
                    "id": eid_str,
                    "threadId": thread_id,
                    "messageId": message_id,
                    "references": references,
                    "sender": from_,
                    "subject": subject,
                    "body": body,
                    "fetch_time": datetime.now().isoformat()  # 读取时间
                }
                self._update_email_status(email_info, status=EmailStatus.UNPROCESSED)
                unanswered_emails.append(email_info)

            mail.logout()
            print(f"{Fore.GREEN} ✅ 读取完成 | 共找到{len(unanswered_emails)}封未处理邮件 {Style.RESET_ALL}")
            return unanswered_emails
        except Exception as e:
            print(f"{Fore.RED} 获取邮件失败: {e} {Style.RESET_ALL}")
            return []
        
    def send_reply(self, initial_email: Email, reply_text: str):
        """
        发送回复邮件, 并更新状态为 AUTO_REPLIED
        """
        try:
            # 1. 校验原始邮件信息
            if not initial_email.id or not initial_email.sender:
                print(f"{Fore.RED} 原始邮件信息不完整缺少id或sender {Style.RESET_ALL}")
                return None
            
            # 2. 创建回复邮件
            reply_msg = self._create_reply_message(initial_email, reply_text, send=True)
            # 优化发件人显示（如“自动回复 <xxx@qq.com>”）
            reply_msg["From"] = f'"AI Reply" <{self.email_account}>'

            server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            
            server.login(self.email_account, self.email_password)
            server.sendmail(self.email_account, initial_email.sender, reply_msg.as_string())
            server.quit()

            # 4. 发送成功：更新状态为 AUTO_REPLIED
            extra_data = {
                "reply_text": reply_text,                  # 回复内容
                "reply_time": datetime.now().isoformat(),  # 发送时间
                "reply_message_id": reply_msg["Message-ID"],  # 回复邮件的ID
                "updated_by": "system"                    # 操作人（系统自动回复）
            }
            # 开发阶段 先不更新状态
            # self._update_email_status(initial_email, status=EmailStatus.AUTO_REPLIED, extra_data=extra_data)

            return {
                "status": "sent",
                "to": initial_email.sender,
                "original_email_id": initial_email.id,
                "reply_message_id": reply_msg["Message-ID"]
            }
        except Exception as e:
            error_msg = f"发送失败：{str(e)}"
            print(f"{Fore.RED}❌ {error_msg} | 原始邮件ID：{initial_email.id}{Style.RESET_ALL}")
            return None
        
    def update_email_category(self, email_id: str, category: str):
        """
        邮件分类后，更新状态为「CATEGORIZED」（已分类）
        :param email_id: 邮件ID（从fetch_unanswered_emails获取）
        :return: 成功True，失败False
        """
        # 1. 校验参数
        if not self.redis_conn or not email_id or not category:
            print("❌ 缺少必要参数（Redis未连接/邮件ID/分类结果）")
            return False

        # 2. 检查邮件是否存在于Redis
        redis_key = self._get_redis_key(email_id)
        if not self.redis_conn.exists(redis_key):
            print(f"❌ 邮件{email_id}不存在于Redis")
            return False

        # 3. 获取邮件基础信息
        email_info = {
            "id": email_id,
            "thread_id": self.redis_conn.hget(redis_key, "thread_id"),
            "sender": self.redis_conn.hget(redis_key, "sender"),
            "subject": self.redis_conn.hget(redis_key, "subject")
        }

        # 4. 更新状态为「CATEGORIZED」
        extra_data = {
            "category": category,                  # 分类结果
            "category_time": datetime.now().isoformat(),  # 分类时间
        }
        self._update_email_status(email_info, status=EmailStatus.CATEGORIZED, extra_data=extra_data)
        return True

    def update_manual_status(self, email_id: str, is_replied: bool, operator: str, reply_note: str = ""):
        """
        更新人工处理状态：MANUAL_PENDING（待人工）或 MANUAL_REPLIED（已人工回复）
        :param is_replied: True=已回复，False=待处理
        :param operator: 操作人（必须填用户名，如"admin"）
        :param reply_note: 人工处理备注（可选）
        """
        if not self.redis_conn or not email_id or not operator:
            print("❌ 缺少必要参数（Redis未连接/邮件ID/操作人）")
            return False

        redis_key = self._get_redis_key(email_id)
        if not self.redis_conn.exists(redis_key):
            print(f"❌ 邮件{email_id}不存在于Redis")
            return False

        # 1. 确定目标状态
        target_status = EmailStatus.MANUAL_REPLIED if is_replied else EmailStatus.MANUAL_PENDING
        # 2. 邮件基础信息
        email_info = {
            "id": email_id,
            "thread_id": self.redis_conn.hget(redis_key, "thread_id"),
            "sender": self.redis_conn.hget(redis_key, "sender"),
            "subject": self.redis_conn.hget(redis_key, "subject")
        }
        # 3. 额外数据（人工处理记录）
        extra_data = {
            "manual_operator": operator,
            "manual_time": datetime.now().isoformat(),
            "manual_note": reply_note,
            "updated_by": operator
        }

        # 4. 更新状态
        self._update_email_status(email_info, status=target_status, extra_data=extra_data)
        return True

    def mark_email_ignored(self, email_id: str, reason: str, operator: str = "system"):
        """
        标记邮件为「IGNORED」已忽略
        :param reason: 忽略原因（如"spam"垃圾邮件、"duplicate"重复邮件）
        """
        if not self.redis_conn or not email_id or not reason:
            print("❌ 缺少必要参数(Redis未连接/邮件ID/忽略原因）")
            return False

        redis_key = self._get_redis_key(email_id)
        if not self.redis_conn.exists(redis_key):
            print(f"❌ 邮件{email_id}不存在于Redis")
            return False

        email_info = {
            "id": email_id,
            "thread_id": self.redis_conn.hget(redis_key, "thread_id"),
            "sender": self.redis_conn.hget(redis_key, "sender"),
            "subject": self.redis_conn.hget(redis_key, "subject")
        }

        extra_data = {
            "ignore_reason": reason,
            "ignore_time": datetime.now().isoformat(),
            "updated_by": operator
        }

        self._update_email_status(email_info, status=EmailStatus.IGNORED, extra_data=extra_data)
        return True

    def _create_reply_message(self, initial_email: Email, reply_text: str, send=False):
        """
        构造 HTML 回复邮件
        """
        msg = MIMEMultipart("alternative")
        # msg["From"] = self.email_account
        msg["To"] = initial_email.sender
        msg["Subject"] = f"Re: {initial_email.subject}" if not initial_email.subject.startswith("Re:") else initial_email.subject

        if initial_email.messageId:
            msg["In-Reply-To"] = initial_email.messageId
            msg["References"] = f"{initial_email.references} {initial_email.messageId}".strip()
        if send:
            msg["Message-ID"] = f"<{uuid.uuid4()}@qq.com>"

        html_text = reply_text.replace("\n", "<br>")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body>{html_text}</body>
        </html>
        """
        msg.attach(MIMEText(html_content, "html", "utf-8"))
        return msg

    def _get_email_body(self, msg):
        """
        提取正文（优先 text/plain，其次 text/html）
        """
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    break
                elif content_type == "text/html":
                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
        else:
            body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

        return self._clean_body_text(body)

    def _clean_body_text(self, text):
        """
        清理正文文本
        """
        return re.sub(r"\s+", " ", text).strip()

    def _get_redis_key(self, email_id: str) -> str:
        """
        生成 Redis 键名
        """
        return f"qqmail:email:status:{email_id}"
    

    def _update_email_status(self, email_info: dict, status: EmailStatus, extra_data: dict = None):
        """
        更新邮件状态
        :param email_info: 邮件基础信息 含id、sender等
        :param status: 目标状态 EmailStatus枚举值
        :param extra_data: 额外数据（如分类结果、人工备注，可选）        
        """
        if not self.redis_conn or not email_info.get("id"):
            print(f"{Fore.YELLOW}⚠️ Redis未连接或邮件信息不完整，跳过状态更新{Style.RESET_ALL}")
            return
                
        base_data = {
            "email_id": email_info["id"],
            "thread_id": email_info.get("threadId", ""),
            "sender": email_info.get("sender", "Unknown"),
            "subject": email_info.get("subject", "No Subject"),
            "status": status.status_value,  # 存储枚举的状态值（如"unprocessed"）
            "status_desc": status.desc,     # 存储中文描述（如"新读取的邮件，未处理"）
            "status_enum": status.name,     # 存储枚举名称（如"UNPROCESSED"，便于排查）
            "updated_at": datetime.now().isoformat(),  # 最后更新时间
            "updated_by": "system"          # 操作人（默认系统，人工处理时可修改）
        }
        if extra_data:
            base_data.update(extra_data)

        redis_key = self._get_redis_key(email_info["id"])
        self.redis_conn.hset(redis_key, mapping=base_data)
        self.redis_conn.expire(redis_key, 60 * 60 * 24 * 30)  # 30天过期

        print(f"{Fore.GREEN} 📧 邮件状态更新 | ID: {email_info['id']} | 状态：{status.name}({status.desc}) {Style.RESET_ALL}")



