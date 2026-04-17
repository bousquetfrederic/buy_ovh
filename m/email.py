import time
import smtplib

from email.message import EmailMessage

import m.config

__all__ = ['send_email', 'send_startup_email']

# from the conf file
email_server_port = m.config.configFile.get('email_server_port', 0)
email_server_name = m.config.configFile.get('email_server_name', "")
email_server_login = m.config.configFile.get('email_server_login', "")
email_server_password = m.config.configFile.get('email_server_password', "")
email_sender = m.config.configFile.get('email_sender', "")
email_receiver = m.config.configFile.get('email_receiver', "")

# send an email
def send_email(subject, text, warnUser=False):

    html = """\
<html>
  <body>
  <div style="font-family: Consolas, 'Courier New', monospace;">
""" + text + """\
  </div>
  </body>
</html>
"""
    try:
        msg = EmailMessage()
        msg['From'] = email_sender
        msg['To'] = email_receiver
        msg['Subject'] = subject
        msg.add_alternative(html, subtype='html')

        # if not in infinite loop, warn the user
        if warnUser:
            print("Sending an email --> " + subject)
        # Send the email
        with smtplib.SMTP(email_server_name, email_server_port) as server:
            server.starttls()
            server.login(email_server_login, email_server_password)
            server.send_message(msg)
    except Exception as e:
        print("Failed to send an email.")
        print(e)
        time.sleep(2)

def send_startup_email():
    send_email("BUY_OVH: startup", "<p>BUY_OVH has started</p>")

def send_auto_buy_email(string):
    send_email("BUY_OVH: autobuy", "<p>" + string + "</p>")
