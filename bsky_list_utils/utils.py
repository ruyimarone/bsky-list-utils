from atproto import Client

from atproto_client import Client, models
from atproto_identity.resolver import IdResolver
from functools import partial
from itertools import islice

import json
import sys
import os

resolver = IdResolver()
BSKY_SP_MAX_SIZE = 150

# Adapted from https://github.com/MarshalX/atproto/blob/main/examples/advanced_usage/add_user_to_list.py
# (CC0)
def get_starter_pack_uri(starterpack_url):
    # starterpacks seem somewhat special in their URL structure
    # "https://bsky.app/starter-pack/marcmarone.com/3lc7gqtydky2m"
    try:
        # Extract the handle and post rkey from the URL
        url_parts = starterpack_url.split('/')
        handle = url_parts[4]  # Username in the URL
        record_key = url_parts[5]  # Record Key in the URL (different location for SPs)
        did = resolver.handle.resolve(handle)
        return f"at://{did}/app.bsky.graph.starterpack/{record_key}"

    except (ValueError, KeyError) as e:
        print(f'Error parsing app URL {starterpack_url}: {e}', file=sys.stderr)
        return None

def handle_and_key_from_url(url):
    try:
        # Extract the handle and post rkey from the URL
        url_parts = url.split('/')
        handle = url_parts[4]  # Username in the URL
        record_type = url_parts[5] # e.g, `list` or `post`
        record_key = url_parts[6]  # Record Key in the URL

        did = resolver.handle.resolve(handle)
        return record_key, did, record_type
    except (ValueError, KeyError) as e:
        print(f'Error parsing app URL {url}: {e}', file=sys.stderr)
        return None

def get_list_items(client, list_uri):
    cursor = None
    while True:
        list_response = client.app.bsky.graph.get_list(params={"list":list_uri, "limit":100, "cursor" : cursor})
        yield from list_response.items
        cursor = list_response.cursor
        if not cursor:
            break

def get_list_items_from_url(client, list_url):
    # turns out I did need this one
    rkey, did, _ = handle_and_key_from_url(list_url)
    list_uri = f"at://{did}/app.bsky.graph.list/{rkey}"
    return list(get_list_items(client, list_uri))

def get_starter_pack_from_url(client, sp_url):
    sp = client.app.bsky.graph.get_starter_pack({"starterPack" : get_starter_pack_uri(sp_url)})
    return list(get_list_items(client, sp.starter_pack.list.uri))

def get_all(function, data_attr, limit=100):
    cursor = None
    data = []
    while True:
        response = function(limit=limit, cursor=cursor)
        batch = getattr(response, data_attr)
        # print(len(batch))
        data.extend(batch)
        cursor = response.cursor
        if not cursor:
            break
    return data

def get_all_likes(client, post_uri):
    fn = partial(client.get_likes, post_uri)
    return get_all(fn, 'likes') 

def get_all_reposts(client, post_uri):
    return get_all(partial(client.get_reposted_by, post_uri), 'reposted_by') 

def get_all_reposts(client, post_uri):
    return get_all(partial(client.get_reposted_by, post_uri), 'reposted_by') 

def get_all_quotes(client, post_uri):
    # for some reason this one needs a lower level api?
    cursor = None
    quotes = []

    while True:
        response = client.app.bsky.feed.get_quotes(params={"uri" : post_uri, "limit" : 100, "cursor" : cursor})
        quotes.extend(response.posts)
        cursor = response.cursor
        if not cursor:
            break
    return quotes


def get_authors(replies, author_did_list):
    for reply in replies:
        author_did_list.append(reply.post.author.did)
        # if this reply has replies, recurse
        if len(reply.replies) > 0:
            get_authors(reply.replies, author_did_list)

def hydrate_profiles(client, list_of_dids):
    it = iter(list_of_dids)
    results = []
    while batch := list(islice(it, 25)):
        results.extend(client.get_profiles(actors=batch).profiles)

    return results


def user_interactions_from_post(client, post):
    # engagements: replies (recursive), likes, reposts, quotes

    thread = client.get_post_thread(post.uri)
    replies = thread.thread.replies

    likes = get_all_likes(client, post.uri)

    reposts = get_all_reposts(client, post.uri)

    quotes = get_all_quotes(client, post.uri)

    # this matches the bsky app interface (reposts, quotes, likes)
    # quotes are different than reposts!
    # print(len(replies), len(likes), len(reposts), len(quotes))

    # Unsure if actors from different engagements will always be the same.
    # Dedupe them on handle, but keep the whole actor object
    # as it contains stuff like bio description
    seen_handles = set()
    seen_actors = []

    for like in likes:
        if like.actor.handle not in seen_handles:
            seen_handles.add(like.actor.handle)
            seen_actors.append(like.actor)

    to_hydrate = []
    # quote post authors are a BasicProfile, I want the profileView that has a description too
    for quote_post in quotes:
        if quote_post.author.handle not in seen_handles:
            seen_handles.add(quote_post.author.handle)
            to_hydrate.append(quote_post.author.did)
        else:
            print("skipping quote post by", quote_post.author.handle, file=sys.stderr)

    for repost in reposts:
        if repost.handle not in seen_handles:
            seen_handles.add(repost.handle)
            seen_actors.append(repost)
        else:
            print("skipping repost by", repost.handle, file=sys.stderr)

    reply_authors = []
    get_authors(replies, reply_authors)
    to_hydrate.extend(reply_authors)

    # unique `did`s
    to_hydrate = list(set(to_hydrate))

    if len(to_hydrate) > 0:
        print(f"Hydrate {len(to_hydrate)} profiles from quotes and replies", file=sys.stderr)
        seen_actors.extend(hydrate_profiles(client, to_hydrate))

    return seen_actors

def add_to_list(client, list_author_did, list_uri, user_to_add_did):
    created_list_item = client.app.bsky.graph.listitem.create(
        list_author_did,
        models.AppBskyGraphListitem.Record(
            list=list_uri,
            subject=user_to_add_did,
            created_at=client.get_current_time_iso(),
        ),
    )
    return created_list_item

def get_client(api_username=None, api_password=None):

    if not api_username:
        api_username = os.environ['BSKY_API_USER']

    if not api_password:
        api_password = os.environ['BSKY_API_PASSWORD']

    client = Client()
    client.login(api_username, api_password)

    return client 