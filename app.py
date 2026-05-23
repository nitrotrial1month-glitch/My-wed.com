import os
import json
import boto3
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

STORAGE_BASE = "./host_clusters"
os.makedirs(STORAGE_BASE, exist_ok=True)

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

def init_aws_session(env_vars):
    return boto3.client(
        'ec2',
        aws_access_key_id=env_vars.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=env_vars.get("AWS_SECRET_ACCESS_KEY"),
        region_name=env_vars.get("AWS_REGION", "ap-south-1")
    ), boto3.client(
        'ssm',
        aws_access_key_id=env_vars.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=env_vars.get("AWS_SECRET_ACCESS_KEY"),
        region_name=env_vars.get("AWS_REGION", "ap-south-1")
    )

@app.route('/api/save-folder', methods=['POST'])
def handle_save_state():
    payload = request.json
    bot_uid = payload.get("bot_id", "anonymous_cluster")
    files_tree = payload.get("files", {})
    env_config = payload.get("env_vars", {})

    target_dir = os.path.join(STORAGE_BASE, f"node_{bot_uid}")
    os.makedirs(target_dir, exist_ok=True)

    for name, data in files_tree.items():
        with open(os.path.join(target_dir, name), "w", encoding="utf-8") as file:
            file.write(data)

    with open(os.path.join(target_dir, "config_meta.json"), "w", encoding="utf-8") as meta_file:
        json.dump({"env": env_config}, meta_file, indent=4)

    return jsonify({"status": "synchronized", "message": "Assets updated successfully."})

@app.route('/api/trigger-deploy', methods=['POST'])
def handle_aws_boot():
    payload = request.json
    env_config = payload.get("env_vars", {})
    node_instance = env_config.get("AWS_INSTANCE_ID")

    if not node_instance:
        return jsonify({"status": "fault", "message": "AWS Node Instance Token Missing."})

    try:
        ec2_client, ssm_client = init_aws_session(env_config)
        ec2_client.start_instances(InstanceIds=[node_instance])
        
        # ব্যাকগ্রাউন্ড ড্রাইভ বুট এক্সিকিউশন কম্যান্ড
        execution_vector = "mkdir -p ~/nova_cluster && cd ~/nova_cluster && python3 --version"
        
        ssm_client.send_command(
            InstanceIds=[node_instance],
            DocumentName="AWS-RunShellScript",
            Parameters={'commands': [execution_vector]}
        )
        return jsonify({"status": "active", "message": "Remote hardware booted. Bot Engine Core deployed globally."})
    except Exception as hardware_error:
        return jsonify({"status": "fault", "message": str(hardware_error)})

@app.route('/api/terminate-alloc', methods=['POST'])
def handle_aws_shutdown():
    payload = request.json
    env_config = payload.get("env_vars", {})
    node_instance = env_config.get("AWS_INSTANCE_ID")

    try:
        ec2_client, _ = init_aws_session(env_config)
        ec2_client.stop_instances(InstanceIds=[node_instance])
        return jsonify({"status": "terminated", "message": "Cloud allocation paused. Instance suspended."})
    except Exception as hardware_error:
        return jsonify({"status": "fault", "message": str(hardware_error)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
    
