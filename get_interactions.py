import json
from bsky_list_utils import handle_and_key_from_url, user_interactions_from_post, get_client

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Get all bsky user interactions on a post")
    parser.add_argument("--url", type=str, help="Post url that you see in browser e.g. https://bsky.app/profile/marcmarone.com/post/3lbnbizbs7s2b")
    parser.add_argument("--api-user", type=str)
    parser.add_argument("--api-password", type=str)
    args = parser.parse_args()

    client = get_client(args.api_user, args.api_password) # will use env variables if these aren't explicitly passed

    rkey, did, _ = handle_and_key_from_url(args.url)
    post = client.get_post(rkey, did)

    for a in user_interactions_from_post(client, post):
        profile_url = f"https://bsky.app/profile/{a.handle}"
        print(json.dumps({"display_name" : a.display_name, "handle" : a.handle, "bio" : a.description, "profile_link" : profile_url, "did" : a.did}, ensure_ascii=False))