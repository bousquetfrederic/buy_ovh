import time
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import m.config

__all__ = ['send_email', 'send_startup_email']

# from the conf file
email_server_port = m.config.configFile['email_server_port'] if 'email_server_port' in m.config.configFile else 0
email_server_name = m.config.configFile['email_server_name'] if 'email_server_name' in m.config.configFile else ""
email_server_login = m.config.configFile['email_server_login'] if 'email_server_login' in m.config.configFile else ""
email_server_password = m.config.configFile['email_server_password'] if 'email_server_password' in m.config.configFile else ""
email_sender = m.config.configFile['email_sender'] if 'email_sender' in m.config.configFile else ""
email_receiver = m.config.configFile['email_receiver'] if 'email_receiver' in m.config.configFile else ""

# send an email
def send_email(subject, text, warnUser=False):

    html = """\
<html>
  <body>
""" + text + """\
  </body>
</html>
"""
    try:
        # Create a multipart message and set headers
        message = MIMEMultipart()
        message["From"] = email_sender
        message["To"] = email_receiver
        message["Subject"] = subject

        # Attach the HTML part
        message.attach(MIMEText(html, "html"))

        # if not in infinite loop, warn the user
        if warnUser:
            print("Sending an email --> " + subject)
        # Send the email
        with smtplib.SMTP(email_server_name, email_server_port) as server:
            server.starttls()
            server.login(email_server_login, email_server_password)
            server.sendmail(email_sender, email_receiver, message.as_string())
    except Exception as e:
        print("Failed to send an email.")
        print(e)
        time.sleep(2)

def send_startup_email():
    send_email("BUY_OVH: startup", "<p>BUY_OVH has started</p>")

def send_auto_buy_email(string):
    send_email("BUY_OVH: autobuy", "<p>" + string + "</p>")
