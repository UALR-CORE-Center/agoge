# Agoge Learner Guide

Welcome to Agoge Cybersecurity Labs. Agoge gives you an isolated or shared cloud environment for hands-on cybersecurity exercises.

> **Agoge terminology**
>
> Your instructor creates a **Lab**. Your individual environment inside that Lab may be labeled a **Workout** in the interface.

## Before you begin

Have the following ready:

- The claim link or direct Workout link supplied by your instructor.
- Your join code, if the Lab uses one.
- The email address your instructor expects you to use.
- A modern browser with pop-ups allowed for the Agoge site.
- An RDP or SSH client if you plan to connect directly. Browser-based Guacamole is available when local clients are restricted.

Lab usernames and passwords are temporary exercise credentials. Do not reuse your personal, institutional, or workplace passwords in Agoge.

## Claim your Lab

If your instructor gave you a direct or LMS link, open it and follow the course instructions. Otherwise:

1. Open the Agoge claim link. The page heading is **Claim Your Lab**.
2. Enter the **Join Code** exactly as your instructor provided it.
3. Enter a valid **Email** address. Use the course or institutional address when your instructor requires it.
4. Click **Submit**.
5. Keep the resulting Workout URL or use the same join code and email later to return to the same environment.

Agoge normalizes the email address and uses it to locate your Workout. The address is visible to your instructor and may also be used for LMS grading. It is not a substitute for authentication, so use the same expected address each time.

## Wait for provisioning

A newly claimed server-based Workout must be provisioned in Google Cloud. The claim page displays **Finding your lab ...**, and the Workout page shows build phases such as **Building Networks**, **Building Servers**, and **Building Firewall Rules**.

Provisioning commonly takes 5–10 minutes, depending on the exercise and current cloud capacity. Keep the page open or save the final URL. If the state becomes **Broken** or does not advance after a reasonable wait, contact your instructor and include the visible state or error message.

## Open the instructions and start the Workout

1. Click **Instructions** near the Lab description. The instructions open in a new tab.
2. Check the state shown beside the session controls.
3. A first server-based session is normally started automatically and runs for roughly two hours.
4. If the state is **Stopped**, choose **Duration (hours)** and click **Start Workout**.
5. Wait for the state to become **Running**. Server **Connect** buttons remain disabled until then.
6. Under **Access Configuration**, wait for either:
   - **This lab is secured for public IP: ...**, or
   - **This lab is available for public access**.

If you change Wi-Fi networks, enable or disable a VPN, or move to a hotspot, your public IP may change. Refresh the Workout page and use **Check Access** when it becomes available so Agoge can authorize the new address.

Web-application-only Labs may not show server or session controls. Open the appropriate button in the **Web Applications** panel instead.

## Connect to a server

The **Servers** table lists each visible server's name, host, IP address, and connection action.

1. Make sure the Workout state is **Running**.
2. Click **Connect** beside the server.
3. Select the configured protocol tab, usually **rdp** or **ssh**.
4. Copy the displayed hostname or command, username, and password.
5. Connect with a local client, or choose **Connect with Guacamole** under **Alternative Connection Method**.

### Recommended clients

| Device | RDP | SSH |
| --- | --- | --- |
| Windows | Built-in **Remote Desktop Connection** | PowerShell or Windows Terminal |
| macOS | [Windows App](https://learn.microsoft.com/en-us/windows-app/get-started-connect-devices-desktops-apps) | Terminal |
| Chromebook | Use **Connect with Guacamole** | Linux or Terminal environment, if your organization enables it |
| Restricted or shared device | Use **Connect with Guacamole** | Use Guacamole when local terminal access is not permitted |

Chrome Remote Desktop is not a general RDP client for an Agoge hostname, username, and password. On a Chromebook, use Guacamole for an RDP-based Lab unless your institution supplies another compatible client.

### RDP

The RDP tab shows **Hostname**, **Username**, and **Password**. Enter those values in your RDP client. Keep the connection modal available until you have copied everything you need.

### SSH

The SSH tab provides a complete **SSH Command** and **User Password**. Run the command in your terminal and enter the password when prompted. Do not share the password or reuse it outside the Lab.

### Guacamole

Click **Connect with Guacamole**. A new tab displays **Apache Guacamole** and **Contacting Server ...** while the browser session is prepared, then redirects automatically.

Guacamole is the preferred fallback when a school or workplace blocks direct RDP or SSH. If Guacamole reports a terminal error, record the message and contact your instructor.

## Use web applications

If the Lab includes browser services, the **Web Applications** panel appears beside the server list. Click the named application to open it in a new tab. A web-application-only Lab may use these buttons as its primary interface.

## Understand expiration and session time

The interface displays two different limits:

| Limit | Meaning | What you can do |
| --- | --- | --- |
| **Expires** | The deadline after which the Lab is no longer available | Contact your instructor before this time if you need an extension |
| **Time Remaining** | How long the currently running servers will stay on | Click **Add one hour** when permitted, or save your work and restart later |

When a session ends or you click **Stop Workout**, files already saved to the server's disk normally remain available for the next session. Unsaved or in-memory work can be lost, and a rebuild or snapshot restore can replace disk contents. Save frequently.

Stopping a Workout conserves cloud resources; it does not extend the **Expires** deadline.

## Complete the assessment

1. Click **Go to Assessment**.
2. Expand **Question 1**, **Question 2**, and each remaining question.
3. Enter the requested response in **Answer 1**, **Answer 2**, and so on.
4. Click **Submit** for each question separately.
5. Check the feedback. A completed question displays a green check and cannot be edited.
6. Click **Back to Workout** when you need to return to the environment.

There is no single final-submit button for the whole assessment. Enter exact values, capitalization, and formatting when the instructions require them. If the page displays **No Questions**, the Lab does not have an Agoge assessment.

## Finish safely

1. Save files inside the server.
2. Submit every required assessment answer or external course artifact.
3. Sign out of any accounts you used inside the Lab.
4. Close RDP, SSH, Guacamole, and web-application sessions.
5. Click **Stop Workout** unless your instructor tells you to leave it running.

## Troubleshooting

| Problem | What to try |
| --- | --- |
| **Join code not found** | Re-enter the code without spaces and confirm it with your instructor |
| Lab capacity has been reached | Contact your instructor for another Lab or other course-specific direction |
| **Finding your lab ...** remains on screen | Allow 5–10 minutes, then refresh once; if it still does not advance, contact your instructor |
| **Connect** is disabled | Wait for the Workout to reach **Running** |
| Direct connection is denied or times out | Wait for **Access Configuration**, refresh after any network or VPN change, then try Guacamole |
| RDP or SSH credentials fail | Copy the values again from **Connect** and make sure you selected the correct protocol tab and server |
| Guacamole remains on **Contacting Server ...** | Wait briefly, then retry once; send the displayed error to your instructor if it fails |
| State is **Expired**, **Broken**, or **Deleted** | Stop retrying and contact your instructor with the exact state |
| Assessment answer is rejected | Re-read the requested format and submit the exact value; ask your instructor if the expected answer appears incorrect |
