import requests
import json
import os
import sys
from config import Config

def upload_rich_menu(json_file_path, image_file_path):
    """
    Uploads a Rich Menu to Line and sets it as the default.
    """
    # 1. Load JSON Config
    if not os.path.exists(json_file_path):
        print(f"Error: JSON file not found at {json_file_path}")
        return
    
    with open(json_file_path, 'r', encoding='utf-8') as f:
        rich_menu_json = json.load(f)

    headers = {
        'Authorization': f'Bearer {Config.LINE_CHANNEL_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }

    # 2. Create Rich Menu Object in Line
    print("Step 1: Creating Rich Menu Object...")
    create_url = 'https://api.line.me/v2/bot/richmenu'
    response = requests.post(create_url, headers=headers, data=json.dumps(rich_menu_json))
    
    if response.status_code != 200:
        print(f"Failed to create rich menu: {response.text}")
        return
        
    rich_menu_id = response.json().get('richMenuId')
    print(f"Success! Rich Menu ID: {rich_menu_id}")

    # 3. Upload Background Image
    print("\nStep 2: Uploading Background Image...")
    if not os.path.exists(image_file_path):
        print(f"Error: Image file not found at {image_file_path}")
        return

    upload_url = f'https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content'
    img_headers = {
        'Authorization': f'Bearer {Config.LINE_CHANNEL_ACCESS_TOKEN}',
        'Content-Type': 'image/png' # or image/jpeg
    }
    
    with open(image_file_path, 'rb') as img:
        img_response = requests.post(upload_url, headers=img_headers, data=img)
        
    if img_response.status_code != 200:
        print(f"Failed to upload image: {img_response.text}")
        return
    print("Success! Image uploaded.")

    # 4. Set as Default Rich Menu for all users
    print("\nStep 3: Setting as Default...")
    default_url = f'https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}'
    def_response = requests.post(default_url, headers=headers)
    
    if def_response.status_code != 200:
        print(f"Failed to set default: {def_response.text}")
        return
    
    print("ALL DONE! Your Rich Menu is now live.")
    print("Note: Close and re-open your LINE app to see the changes.")

if __name__ == "__main__":
    # การใช้งาน: python src/upload_rich_menu.py [path_to_json] [path_to_image]
    # ตัวอย่าง: python src/upload_rich_menu.py line_ux/rich_menu.json line_ux/rich_menu.png
    if len(sys.argv) < 3:
        print("Usage: python src/upload_rich_menu.py line_ux/rich_menu.json Images/rich_menu.png")
    else:
        upload_rich_menu(sys.argv[1], sys.argv[2])
