DEFAULT_SERVER_IMAGES = {
  "image-csec1310-powershell": {
    "name": "csec1310-powershell",
    "machine_type": "e2-standard-2",
    "description": "Generic Windows 2022 host for powershell commands",
    "tags": [
      ""
    ],
    "image": "image-csec1310-powershell",
    "os": "windows",
    "add_disk": "50",
    "disks": [
      {
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
          "sourceImage": "projects/{project}/global/images/image-csec1310-powershell",
          "diskSizeGb": 50,
          "type": "projects/{project}/zones/{zone}/diskType/pd-standard"
        }
      }
    ],
    "human_interaction": [
      {
        "display": True,
        "protocol": "rdp",
        "username": "cyberarena",
        "password": "pTLV|p<Am\\<Nd5y",
        "ssh_key": None,
        "domain": None,
        "security_mode": "nla"
      },
      {
        "display": False,
        "protocol": "ssh",
        "username": "cyberarena",
        "password": "pTLV|p<Am\\<Nd5y",
        "ssh_key": None,
        "domain": None,
        "security_mode": "nla"
      }
    ],
    "status": 0,
    "services": [
      "Powershell",
      "Windows 2022",
      "RDP"
    ],
    "self_link": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-csec1310-powershell",
    "dns_record": None,
    "in_use_by": None,
    "state": 1,
    "state_timestamp": None,
    "base_family": [
      None
    ],
    "image_exists": False
  },
  "image-csec3300-final": {
    "name": "csec3300-final",
    "machine_type": "e2-standard-4",
    "description": "Digital Forensics Workstation\n",
    "tags": [
      "http-server",
      "https-server"
    ],
    "image": "image-csec3300-final",
    "os": "windows",
    "add_disk": "100",
    "disks": [
      {
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
          "sourceImage": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-csec3300-final",
          "diskSizeGb": 100,
          "type": "projects/{project}/zones/{zone}/diskTypes/pd-standard"
        }
      }
    ],
    "human_interaction": [],
    "status": 0,
    "services": [
      "RDP"
    ],
    "self_link": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-csec3300-final",
    "dns_record": None,
    "in_use_by": None,
    "state": 0,
    "state_timestamp": None,
    "base_family": [
      None
    ],
    "image_exists": False
  },
  "image-csec3314-powershell": {
    "name": "csec3314-powershell",
    "machine_type": "e2-standard-2",
    "description": "Student Windows 2022 host with RDP and IR tools installed.\n",
    "tags": [
      "http-server",
      "https-server"
    ],
    "image": "image-csec3314-powershell",
    "os": "windows",
    "add_disk": "100",
    "disks": [
      {
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
          "sourceImage": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-csec3314-powershell",
          "diskSizeGb": 100,
          "type": "projects/{project}/zones/{zone}/diskTypes/pd-standard"
        }
      }
    ],
    "human_interaction": [],
    "status": 0,
    "services": [
      "rdp",
      "gui"
    ],
    "self_link": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-csec3314-powershell",
    "dns_record": None,
    "in_use_by": None,
    "state": 0,
    "state_timestamp": None,
    "base_family": [
      None
    ],
    "image_exists": False
  },
  "image-cyberarena-csec2324-student": {
    "name": "cyberarena-csec2324-student",
    "machine_type": "e2-medium",
    "description": "Student Linux computer\n",
    "tags": [
      "http-server",
      "https-server"
    ],
    "image": "image-cyberarena-csec2324-student",
    "os": "linux",
    "add_disk": "30",
    "disks": [
      {
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
          "sourceImage": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-cyberarena-csec2324-student",
          "diskSizeGb": 30,
          "type": "projects/{project}/zones/{zone}/diskTypes/pd-standard"
        }
      }
    ],
    "human_interaction": [],
    "status": 1,
    "services": [
      "wireshark",
      "rdp",
      "gui"
    ],
    "self_link": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-cyberarena-csec2324-student",
    "dns_record": "cyberarena-csec2324-student.test-cybergym.org.",
    "in_use_by": "Patrick Roberts",
    "state": 6,
    "state_timestamp": None,
    "base_family": [
      None
    ],
    "image_exists": False
  },
  "image-cyberarena-lamp": {
    "name": "cyberarena-lamp",
    "machine_type": "e2-medium",
    "description": "Basic Linux server with Apache and MySQL logs\n",
    "tags": [
      "http-server",
      "https-server"
    ],
    "image": "image-cyberarena-lamp",
    "os": "linux",
    "add_disk": "15",
    "disks": [
      {
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
          "sourceImage": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-cyberarena-lamp",
          "diskSizeGb": 15,
          "type": "projects/{project}/zones/{zone}/diskTypes/pd-standard"
        }
      }
    ],
    "human_interaction": [],
    "status": 0,
    "services": [
      "MySQL",
      "Apache",
      "ssh"
    ],
    "self_link": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-cyberarena-lamp",
    "dns_record": None,
    "in_use_by": None,
    "state": 0,
    "state_timestamp": None,
    "base_family": [
      None
    ],
    "image_exists": False
  },
  "image-cyberarena-sliver-implant": {
    "name": "cyberarena-sliver-implant",
    "machine_type": "e2-medium",
    "description": "Vulnerable Windows server with pre-installed Sliver-Implant\n",
    "tags": [
      "http-server",
      "https-server"
    ],
    "image": "image-cyberarena-sliver-implant",
    "os": "windows",
    "add_disk": "50",
    "disks": [
      {
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
          "sourceImage": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-cyberarena-sliver-implant",
          "diskSizeGb": 50,
          "type": "projects/{project}/zones/{zone}/diskTypes/pd-standard"
        }
      }
    ],
    "human_interaction": [],
    "status": 0,
    "services": [
      "sliver-implant",
      "wireshark",
      "rdp",
      "gui"
    ],
    "self_link": None,
    "dns_record": None,
    "in_use_by": None,
    "state": 0,
    "state_timestamp": None,
    "base_family": [
      None
    ],
    "image_exists": False
  },
  "image-cyberarena-win-sectools": {
    "name": "cyberarena-win-sectools",
    "machine_type": "e2-medium",
    "description": "Attacker machine with Slowloris and WinSCP.\n",
    "tags": [
      "deny-outbound"
    ],
    "image": "image-cyberarena-win-sectools",
    "os": "windows",
    "add_disk": "100",
    "disks": [
      {
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
          "sourceImage": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-cyberarena-win-sectools",
          "diskSizeGb": 100,
          "type": "projects/{project}/zones/{zone}/diskTypes/pd-standard"
        }
      }
    ],
    "human_interaction": [],
    "status": 1,
    "services": [
      "Slowloris",
      "WinSCP",
      "RDP"
    ],
    "self_link": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-cyberarena-win-sectools",
    "dns_record": "cyberarena-win-sectools.test-cybergym.org.",
    "in_use_by": "pdhuff@ualr.edu",
    "state": 6,
    "state_timestamp": None,
    "base_family": [
      None
    ],
    "image_exists": False
  },
  "image-cybergym-lostpuppy": {
    "name": "cybergym-lostpuppy",
    "machine_type": "e2-medium",
    "description": "Windows server serving Cellebrite and a mobile forensics image\n",
    "tags": [
      "http-server",
      "https-server"
    ],
    "image": "image-cybergym-lostpuppy",
    "os": "windows",
    "add_disk": "100",
    "disks": [
      {
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
          "sourceImage": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-cybergym-lostpuppy",
          "diskSizeGb": 100,
          "type": "projects/{project}/zones/{zone}/diskTypes/pd-standard"
        }
      }
    ],
    "human_interaction": [],
    "status": 0,
    "services": [
      "Cellebrite",
      "forensics image",
      "rdp"
    ],
    "self_link": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-cybergym-lostpuppy",
    "dns_record": None,
    "in_use_by": None,
    "state": 0,
    "state_timestamp": None,
    "base_family": [
      None
    ],
    "image_exists": False
  },
  "image-cybergym-nessus": {
    "name": "cybergym-nessus",
    "machine_type": "n1-standard-2",
    "description": "Nessus server with RDP and Nessus installed.\n",
    "tags": [
      "dns",
      "http-server",
      "https-server"
    ],
    "image": "image-cybergym-nessus",
    "os": "windows",
    "add_disk": "50",
    "disks": [
      {
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
          "sourceImage": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-cybergym-nessus",
          "diskSizeGb": 50,
          "type": "projects/{project}/zones/{zone}/diskTypes/pd-standard"
        }
      }
    ],
    "human_interaction": [],
    "status": 0,
    "services": [
      "rdp",
      "gui"
    ],
    "self_link": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-cybergym-nessus",
    "dns_record": None,
    "in_use_by": None,
    "state": 0,
    "state_timestamp": None,
    "base_family": [
      None
    ],
    "image_exists": False
  },
  "image-cybergym-teenyweb": {
    "name": "cybergym-teenyweb",
    "machine_type": "e2-small",
    "description": "Server hosting insecure Apache web service\n",
    "tags": [
      "http-server",
      "https-server"
    ],
    "image": "image-cybergym-teenyweb",
    "os": "linux",
    "add_disk": "10",
    "disks": [
      {
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
          "sourceImage": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-cybergym-teenyweb",
          "diskSizeGb": 10,
          "type": "projects/{project}/zones/{zone}/diskTypes/pd-standard"
        }
      }
    ],
    "human_interaction": [],
    "status": 0,
    "services": [
      "apache web server",
      "ssh"
    ],
    "self_link": None,
    "dns_record": None,
    "in_use_by": None,
    "state": 0,
    "state_timestamp": None,
    "base_family": [
      None
    ],
    "image_exists": False
  },
  "image-forensics-workstation-szechuan": {
    "name": "forensics-workstation-szechuan",
    "machine_type": "e2-standard-2",
    "description": "Windows server hosting various digital forensics tools\n",
    "tags": [
      "http-server",
      "https-server"
    ],
    "image": "image-forensics-workstation-szechuan",
    "os": "windows",
    "add_disk": "50",
    "disks": [
      {
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
          "sourceImage": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-forensics-workstation-szechuan",
          "diskSizeGb": 50,
          "type": "projects/{project}/zones/{zone}/diskTypes/pd-standard"
        }
      }
    ],
    "human_interaction": [],
    "status": 0,
    "services": [
      "Autopsy",
      "FTKImager",
      "Registry Viewer",
      "Kape"
    ],
    "self_link": None,
    "dns_record": None,
    "in_use_by": None,
    "state": 0,
    "state_timestamp": None,
    "base_family": [
      None
    ],
    "image_exists": False
  },
  "image-ghost-chair": {
    "name": "ghost-chair",
    "machine_type": "e2-micro",
    "description": "Testing community servers",
    "tags": [
      "https-server",
      "http-server"
    ],
    "image": "image-ghost-chair",
    "os": "linux",
    "add_disk": "10",
    "disks": [
      {
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
          "sourceImage": "https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/ubuntu-2404-noble-amd64-v20241004",
          "diskSizeGb": 10,
          "type": "projects/{project}/zones/{zone}/diskTypes/pd-standard"
        }
      }
    ],
    "human_interaction": [],
    "status": 1,
    "services": [],
    "self_link": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-ghost-chair",
    "dns_record": "ghost-chair.test-cybergym.org.",
    "in_use_by": "proberts1@ualr.edu",
    "state": 6,
    "state_timestamp": None,
    "base_family": "ubuntu-2404-lts-amd64",
    "image_exists": False
  },
  "image-kali-linux-2023": {
    "name": "kali-linux-2023",
    "machine_type": "e2-standard-2",
    "description": "Student Kali Linux host with xRDP and Nessus installed.\n",
    "tags": [
      "http-server",
      "https-server"
    ],
    "image": "image-kali-linux-2023",
    "os": "linux",
    "add_disk": "50",
    "disks": [
      {
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
          "sourceImage": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/kali-linux-2023",
          "diskSizeGb": 50,
          "type": "projects/{project}/zones/{zone}/diskTypes/pd-standard"
        }
      }
    ],
    "human_interaction": [],
    "status": 0,
    "services": [
      "nessus",
      "rdp",
      "gui"
    ],
    "self_link": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-kali-linux-2023",
    "dns_record": "kali-linux-2023.test-cybergym.org.",
    "in_use_by": None,
    "state": 0,
    "state_timestamp": None,
    "base_family": [
      None
    ],
    "image_exists": False
  }
}
