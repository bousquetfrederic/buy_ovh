import time
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import m.global_variables as GV

# send an email
def sendEmail(subject,text):

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
        message["From"] = GV.email_sender
        message["To"] = GV.email_receiver
        message["Subject"] = subject

        # Attach the HTML part
        message.attach(MIMEText(html, "html"))

        # if not in infinite loop, warn the user
        if not GV.loop:
            print("Sending an email --> " + subject)
        # Send the email
        with smtplib.SMTP(GV.email_server_name, GV.email_server_port) as server:
            server.starttls()
            server.login(GV.email_server_login, GV.email_server_password)
            server.sendmail(GV.email_sender, GV.email_receiver, message.as_string())
    except Exception as e:
        print("Failed to send an email.")
        print(e)
        time.sleep(2)

def sendStartupEmail():
    sendEmail("BUY_OVH: startup", "<p>BUY_OVH has started</p>")

def sendAutoBuyEmail(string):
    sendEmail("BUY_OVH: autobuy", "<p>" + string + "</p>")
