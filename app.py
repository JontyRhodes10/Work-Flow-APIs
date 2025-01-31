from fastapi import FastAPI, HTTPException,Request
from pydantic import BaseModel
import requests
from requests.auth import HTTPBasicAuth
import json
from bs4 import BeautifulSoup
from typing import Optional
import logging

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)

app = FastAPI(title="WordPress Post Creator API")

class WordPressPost(BaseModel):
    title: str
    content: str
    url: str
    status: str = "draft"
    username: str
    apikey: str

@app.post("/posttowordpress")
async def create_wordpress_post(post: WordPressPost):
    try:
        wp_api_url = f"{post.url.rstrip('/')}/wp-json/wp/v2/posts"
        headers = {"Accept": "application/json","Content-Type": "application/json"}
        payload = json.dumps({"title": post.title,"content": post.content,"status": post.status})
        response = requests.post(
            wp_api_url,
            data=payload,
            headers=headers,
            auth=HTTPBasicAuth(post.username, post.apikey)
        )
        response.raise_for_status()
        return {
            "status": "success",
            "message": "Post created successfully",
            "post_data": response.json()
        }
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error posting to WordPress: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

def get_image_url(image_path: str, api_key: str) -> Optional[str]:
    try:
        payload = {
            'key': api_key,
            'source': image_path,
            'action': 'upload'
        }
        response = requests.post("https://freeimage.host/api/1/upload", data=payload)
        if response.ok:
            data = response.json()
            return data.get('image', {}).get('url')
    except Exception as e:
        print(f"Error processing image URL: {e}")
    
    return None

def integrate_images(content: str, featured_image: str, image1: str, image2: str, api_key: str) -> str:
    if not content:
        return content
    featured_url = get_image_url(featured_image, api_key)
    image1_url = get_image_url(image1, api_key)
    image2_url = get_image_url(image2, api_key)
    soup = BeautifulSoup(content, 'html.parser')
    text_content = soup.get_text()
    total_length = len(text_content)
    fifty_percent_point = int(total_length * 0.5)
    eighty_percent_point = int(total_length * 0.8)
    img_featured = soup.new_tag('img', 
                               src=featured_url if featured_url else featured_image,
                               alt="Featured Image", 
                               style="height: 550px;")
    first_p = soup.find('p')
    if first_p:
        first_p.insert_before(img_featured)
    else:
        if soup.body:
            soup.body.insert(0, img_featured)
        else:
            soup.insert(0, img_featured)
    current_length = 0
    last_h2_before_fifty = None
    last_p_before_eighty = None
    for tag in soup.find_all(['p', 'h2']):
        current_length += len(tag.get_text())
        if current_length <= fifty_percent_point and tag.name == 'h2':
            last_h2_before_fifty = tag
        if current_length <= eighty_percent_point and tag.name == 'p':
            last_p_before_eighty = tag
    if last_h2_before_fifty and image1:
        img_1 = soup.new_tag('img',
                            src=image1_url if image1_url else image1,
                            alt="Image 1",
                            style="height: 50%")
        last_h2_before_fifty.insert_before(img_1)
    if last_p_before_eighty and image2:
        img_2 = soup.new_tag('img',
                            src=image2_url if image2_url else image2,
                            alt="Image 2",
                            style="height: 50%")
        if last_p_before_eighty.next_sibling:
            last_p_before_eighty.insert_after(img_2)
        else:
            last_p_before_eighty.parent.append(img_2)
    return str(soup)

@app.post("/integrate-images")
async def integrate_images_endpoint(request: Request):
    try:
        body = await request.json()
        data = body[0] if isinstance(body, list) else body
        
        content = data.get('Content', '')
        featured_image = data.get('featured image', '')
        image1 = data.get('Image 1', '')
        image2 = data.get('Image 2', '')
        api_key=data.get('Api_Key','')
        
        if not all([content, featured_image, image1,api_key]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        modified_content = integrate_images(content, featured_image, image1, image2,api_key)
        return {"modified_content": modified_content}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
