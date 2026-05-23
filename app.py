
import os
import json
import boto3
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

# ডেটা স্টোরেজ পাথ
PROJECTS_DIR = "./user_projects"
os.makedirs(PROJECTS_DIR, exist_ok=True)

# হোম রুট লজিক: ইনডেক্স ফাইল সার্ভ করা
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# 🧠 ১. AWS ক্লায়েন্ট জেনারেটর মেথড
def get_aws_services(env_vars):
    access_key = env_vars.get("AWS_ACCESS_KEY_ID")
    secret_key = env_vars.get("AWS_SECRET_ACCESS_KEY")
    region = env_vars.get("AWS_REGION", "ap-south-1")
    
    ec2 = boto3.client('ec2', aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name=region)
    ssm = boto3.client('ssm', aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name=region)
    return ec2, ssm

# 📂 ২. গ্লোবাল ফোল্ডার সেভ বাটন এপিআই (Save Whole Folder)
@app.route('/api/save-folder', methods=['POST'])
def save_folder():
    data = request.json
    bot_id = data.get("bot_id", "default_user")
    files = data.get("files", {}) # {"main.py": "code...", "moderation.py": "code..."}
    env_vars = data.get("env_vars", {})

    bot_dir = os.path.join(PROJECTS_DIR, f"bot_{bot_id}")
    os.makedirs(bot_dir, exist_ok=True)

    # সব কোড ফাইল একসাথে নো-ফোল্ডার লজিকে সেভ করা
    for file_name, file_content in files.items():
        with open(os.path.join(bot_dir, file_name), "w", encoding="utf-8") as f:
            f.write(file_content)

    # Env ভ্যারিয়েবল মেটা ফাইল আকারে সেভ করা
    with open(os.path.join(bot_dir, "config_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"env": env_vars}, f, indent=4)

    return jsonify({"status": "success", "message": "💾 Whole folder and environment synced locally!"})

# 🟢 ৩. Trigger Deployment (টার্মিনাল ছাড়া AWS রান করার বাটন)
@app.route('/api/trigger-deploy', methods=['POST'])
def trigger_deploy():
    data = request.json
    bot_id = data.get("bot_id", "default_user")
    env_vars = data.get("env_vars", {})
    instance_id = env_vars.get("AWS_INSTANCE_ID")

    if not instance_id:
        return jsonify({"status": "error", "message": "❌ Missing AWS_INSTANCE_ID in Env Panel!"})

    try:
        ec2, ssm = get_aws_services(env_vars)
        
        # কদম ১: AWS EC2 ইনস্ট্যান্স স্টার্ট করা
        print(f"Booting up AWS Instance: {instance_id}")
        ec2.start_instances(InstanceIds=[instance_id])
        
        # কদম ২: কন্টেইনার বা রানটাইমে কোড এক্সিকিউট করার জন্য AWS SSM কমান্ড পাঠানো
        # ইউজারকে কোনো SSH বা টার্মিনালে ঢুকতেই হবে না
        # (এখানে উদাহরণ হিসেবে একটি ডিরেক্টরি তৈরি করে রান করার লজিক দেওয়া হয়েছে)
        ssm_command = "mkdir -p ~/bot && echo 'AWS Node Triggered' && python3 --version"
        
        response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={'commands': [ssm_command]}
        )
        
        return jsonify({
            "status": "success", 
            "message": "🟢 AWS Server Activated! Bot deployment package sequence initiated successfully."
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"❌ AWS API Error: {str(e)}"})

# 🔴 ৪. Terminate Allocation (AWS সার্ভার স্টপ করার বাটন)
@app.route('/api/terminate-alloc', methods=['POST'])
def terminate_alloc():
    data = request.json
    env_vars = data.get("env_vars", {})
    instance_id = env_vars.get("AWS_INSTANCE_ID")

    if not instance_id:
        return jsonify({"status": "error", "message": "❌ Missing AWS_INSTANCE_ID!"})

    try:
        ec2, _ = get_aws_services(env_vars)
        ec2.stop_instances(InstanceIds=[instance_id])
        return jsonify({"status": "success", "message": "🔴 AWS Instance suspended successfully. Billing paused."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
  
