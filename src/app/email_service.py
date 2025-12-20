"""
Email Delivery Service for PodcastOS.

Supports multiple providers:
- SendGrid (recommended for production)
- AWS SES
- SMTP (Gmail, etc.)

For demo/development, saves emails to local files.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import logging
import json

from pydantic import BaseModel, EmailStr


logger = logging.getLogger(__name__)


class EmailRecipient(BaseModel):
    """Email recipient."""
    email: str
    name: Optional[str] = None


class EmailMessage(BaseModel):
    """Email message to send."""
    to: List[EmailRecipient]
    subject: str
    html_content: str
    plain_text: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None


class EmailResult(BaseModel):
    """Result of email send."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    recipients_count: int = 0


class EmailService:
    """
    Email delivery service with multiple provider support.

    Priority:
    1. SendGrid (if SENDGRID_API_KEY set)
    2. AWS SES (if AWS credentials set)
    3. SMTP (if SMTP_HOST set)
    4. Local file (demo mode)
    """

    def __init__(self, output_dir: str = "./output/emails"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Determine provider
        self.provider = self._detect_provider()
        logger.info(f"Email service using provider: {self.provider}")

    def _detect_provider(self) -> str:
        """Detect which email provider to use."""
        if os.getenv("RESEND_API_KEY"):
            return "resend"
        elif os.getenv("SENDGRID_API_KEY"):
            return "sendgrid"
        elif os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SES_REGION"):
            return "ses"
        elif os.getenv("SMTP_HOST"):
            return "smtp"
        else:
            return "local"

    async def send(self, message: EmailMessage) -> EmailResult:
        """Send an email message."""
        if self.provider == "resend":
            return await self._send_resend(message)
        elif self.provider == "sendgrid":
            return await self._send_sendgrid(message)
        elif self.provider == "ses":
            return await self._send_ses(message)
        elif self.provider == "smtp":
            return await self._send_smtp(message)
        else:
            return await self._send_local(message)

    async def send_newsletter(
        self,
        newsletter_html: str,
        subject: str,
        recipients: List[str],
        from_email: str = None,
        from_name: str = "PodcastOS",
    ) -> EmailResult:
        """
        Convenience method to send a newsletter.

        Args:
            newsletter_html: The HTML content of the newsletter
            subject: Email subject line
            recipients: List of email addresses
            from_email: Sender email (defaults to env var)
            from_name: Sender name
        """
        message = EmailMessage(
            to=[EmailRecipient(email=r) for r in recipients],
            subject=subject,
            html_content=newsletter_html,
            from_email=from_email or os.getenv("FROM_EMAIL", "newsletter@podcastos.com"),
            from_name=from_name,
        )

        return await self.send(message)

    async def _send_resend(self, message: EmailMessage) -> EmailResult:
        """Send via Resend."""
        try:
            import resend

            resend.api_key = os.getenv("RESEND_API_KEY")

            # Resend requires a verified domain, use their test domain for dev
            from_email = message.from_email or os.getenv("FROM_EMAIL", "onboarding@resend.dev")
            from_name = message.from_name or "PodcastOS"

            response = resend.Emails.send({
                "from": f"{from_name} <{from_email}>",
                "to": [r.email for r in message.to],
                "subject": message.subject,
                "html": message.html_content,
            })

            return EmailResult(
                success=True,
                message_id=response.get("id"),
                recipients_count=len(message.to),
            )

        except Exception as e:
            logger.error(f"Resend error: {e}")
            return EmailResult(success=False, error=str(e))

    async def _send_sendgrid(self, message: EmailMessage) -> EmailResult:
        """Send via SendGrid."""
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content

            sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))

            from_email = Email(
                message.from_email or os.getenv("FROM_EMAIL"),
                message.from_name
            )

            to_emails = [To(r.email, r.name) for r in message.to]

            mail = Mail(
                from_email=from_email,
                to_emails=to_emails,
                subject=message.subject,
                html_content=Content("text/html", message.html_content),
            )

            if message.plain_text:
                mail.add_content(Content("text/plain", message.plain_text))

            response = sg.send(mail)

            return EmailResult(
                success=response.status_code in [200, 201, 202],
                message_id=response.headers.get("X-Message-Id"),
                recipients_count=len(message.to),
            )

        except Exception as e:
            logger.error(f"SendGrid error: {e}")
            return EmailResult(success=False, error=str(e))

    async def _send_ses(self, message: EmailMessage) -> EmailResult:
        """Send via AWS SES."""
        try:
            import boto3

            ses = boto3.client(
                "ses",
                region_name=os.getenv("AWS_SES_REGION", "us-east-1"),
            )

            response = ses.send_email(
                Source=f"{message.from_name} <{message.from_email}>",
                Destination={
                    "ToAddresses": [r.email for r in message.to],
                },
                Message={
                    "Subject": {"Data": message.subject},
                    "Body": {
                        "Html": {"Data": message.html_content},
                        "Text": {"Data": message.plain_text or ""},
                    },
                },
            )

            return EmailResult(
                success=True,
                message_id=response["MessageId"],
                recipients_count=len(message.to),
            )

        except Exception as e:
            logger.error(f"SES error: {e}")
            return EmailResult(success=False, error=str(e))

    async def _send_smtp(self, message: EmailMessage) -> EmailResult:
        """Send via SMTP."""
        try:
            smtp_host = os.getenv("SMTP_HOST")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            smtp_user = os.getenv("SMTP_USER")
            smtp_pass = os.getenv("SMTP_PASS")

            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = f"{message.from_name} <{message.from_email}>"
            msg["To"] = ", ".join([r.email for r in message.to])

            if message.plain_text:
                msg.attach(MIMEText(message.plain_text, "plain"))
            msg.attach(MIMEText(message.html_content, "html"))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            return EmailResult(
                success=True,
                recipients_count=len(message.to),
            )

        except Exception as e:
            logger.error(f"SMTP error: {e}")
            return EmailResult(success=False, error=str(e))

    async def _send_local(self, message: EmailMessage) -> EmailResult:
        """Save email locally (demo mode)."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"email_{timestamp}.html"
            filepath = self.output_dir / filename

            # Create a preview wrapper
            preview_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Email Preview: {message.subject}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; background: #f5f5f5; padding: 20px; }}
        .meta {{ background: #333; color: white; padding: 20px; border-radius: 10px 10px 0 0; }}
        .meta p {{ margin: 5px 0; }}
        .content {{ background: white; padding: 0; border-radius: 0 0 10px 10px; }}
    </style>
</head>
<body>
    <div class="meta">
        <p><strong>To:</strong> {', '.join([r.email for r in message.to])}</p>
        <p><strong>From:</strong> {message.from_name} &lt;{message.from_email}&gt;</p>
        <p><strong>Subject:</strong> {message.subject}</p>
        <p><strong>Sent:</strong> {datetime.now().isoformat()}</p>
        <p style="color: #00ff88;"><strong>Mode:</strong> Demo (saved locally)</p>
    </div>
    <div class="content">
        {message.html_content}
    </div>
</body>
</html>
"""

            with open(filepath, "w") as f:
                f.write(preview_html)

            logger.info(f"Email saved locally: {filepath}")

            return EmailResult(
                success=True,
                message_id=f"local_{timestamp}",
                recipients_count=len(message.to),
            )

        except Exception as e:
            logger.error(f"Local save error: {e}")
            return EmailResult(success=False, error=str(e))


# Subscriber management (simple file-based for demo)
class SubscriberList:
    """Simple subscriber list management."""

    def __init__(self, file_path: str = "./output/subscribers.json"):
        self.file_path = Path(file_path)
        self._ensure_file()

    def _ensure_file(self):
        """Ensure subscriber file exists."""
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w") as f:
                json.dump({"subscribers": []}, f)

    def add(self, email: str, name: str = None) -> bool:
        """Add a subscriber."""
        data = self._load()
        if email not in [s["email"] for s in data["subscribers"]]:
            data["subscribers"].append({
                "email": email,
                "name": name,
                "subscribed_at": datetime.now().isoformat(),
            })
            self._save(data)
            return True
        return False

    def remove(self, email: str) -> bool:
        """Remove a subscriber."""
        data = self._load()
        original_count = len(data["subscribers"])
        data["subscribers"] = [s for s in data["subscribers"] if s["email"] != email]
        if len(data["subscribers"]) < original_count:
            self._save(data)
            return True
        return False

    def list_all(self) -> List[str]:
        """Get all subscriber emails."""
        data = self._load()
        return [s["email"] for s in data["subscribers"]]

    def count(self) -> int:
        """Get subscriber count."""
        return len(self.list_all())

    def _load(self) -> dict:
        with open(self.file_path, "r") as f:
            return json.load(f)

    def _save(self, data: dict):
        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=2)


# Convenience function
async def send_newsletter_email(
    html_content: str,
    subject: str,
    to_emails: List[str],
) -> EmailResult:
    """Quick function to send a newsletter."""
    service = EmailService()
    return await service.send_newsletter(
        newsletter_html=html_content,
        subject=subject,
        recipients=to_emails,
    )
