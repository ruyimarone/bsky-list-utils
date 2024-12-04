from bsky_list_utils import handle_and_key_from_url, get_client, \
    user_interactions_from_post, get_starter_pack_from_url, \
    get_list_items_from_url, get_all_likes

example_post = "https://bsky.app/profile/marcmarone.com/post/3lbnbizbs7s2b"
example_starter_pack = "https://bsky.app/starter-pack/marcmarone.com/3lbn6teyljo2e"
example_list = "https://bsky.app/profile/marcmarone.com/lists/3lbn7mqk33e2b"


client = get_client()

# List users who engaged with a post
# This includes Likes, Quotes, Reposts, and Replies
# i.e. the engagements listed in the bluesky UI

record_key, did, _ = handle_and_key_from_url(example_post)
post = client.get_post(record_key, did)
for user in user_interactions_from_post(client, post)[:10]:
    print(user.display_name)

# List users in a starter pack:
for sp_item in get_starter_pack_from_url(client, example_starter_pack)[:10]:
    print(sp_item.subject.display_name)

# List users in a normal list
for list_item in get_list_items_from_url(client, example_list)[:10]:
    print(list_item.subject.handle)

# get likes on a post
for like in get_all_likes(client, post.uri)[:10]:
    print(like.actor.handle)
    print(like.actor.description)
