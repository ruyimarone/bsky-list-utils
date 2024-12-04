import os
import json
import itertools

from bsky_list_utils import handle_and_key_from_url, get_starter_pack_uri, get_list_items, get_client, add_to_list, BSKY_SP_MAX_SIZE

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sync a bluesky list to one or more starterpacks")
    parser.add_argument("--list-url", type=str, help="List url")
    parser.add_argument("--sp-urls", type=str, help="Starterpack url(s)", nargs="+")
    parser.add_argument("--api-user", type=str)
    parser.add_argument("--api-password", type=str)
    parser.add_argument("--commit", action='store_true', help="Add --commit to actually change lists. Otherwise defaults to a dry run.")
    args = parser.parse_args()

    client = get_client()

    # get all dids from the input list
    rkey, did, _ = handle_and_key_from_url(args.list_url)
    source_list_uri = f"at://{did}/app.bsky.graph.list/{rkey}"

    source_list = list(get_list_items(client, source_list_uri)) # all the users we want to eventually add
    did_to_handle = {l.subject.did : l.subject.handle for l in source_list} # map from did to handle
    source_list_dids = [l.subject.did for l in source_list]
    did_to_sp = {} # need this to track which users are already in which SPs - for later removal

    already_present_dids = set()
    uri_to_size = {}

    for sp_url in args.sp_urls:
        sp_uri = get_starter_pack_uri(sp_url)
        sp = client.app.bsky.graph.get_starter_pack({"starterPack" : sp_uri})
        sp_list_uri = sp.starter_pack.list.uri

        list_items = list(get_list_items(client, sp_list_uri))
        print(sp.starter_pack.record.description)
        print(f"Has {len(list_items)} users")
        print('-' * 80)

        # store the unique dids and remember how large each starter pack already was
        already_present_dids.update(set(l.subject.did for l in list_items))
        uri_to_size[sp_list_uri] = len(list_items)

    # remove dids that are already present in some starter pack
    to_add_dids = [did for did in source_list_dids if did not in already_present_dids]

    print(f"There are {len(to_add_dids)} new users out of {len(source_list_dids)}")

    to_add_dids = iter(to_add_dids)
    # We know how many slots are available in each SP. So add that many people.
    # We know we ran out of space if the loop below finishes and the iterator still contains some folks to add
    for list_uri, initial_size in uri_to_size.items():
        print("-" * 80)
        print(f"Checking for space in sp {list_uri}")
        capacity = BSKY_SP_MAX_SIZE - 5 - initial_size # buffer of 5 spaces
        if capacity <= 0:
            print(f"Skipping new additions for {list_uri} because it is already full")
            continue

        # slice off some names to add
        print(f"Has capacity for {capacity} new users")
        batch = list(itertools.islice(to_add_dids, capacity))
        print(f"There were {len(batch)} actual users to add")
        if len(batch) == 0:
            print("Done consuming users to add")
            continue

        for user_did in batch:
            if args.commit:
                add_to_list(client, list_author_did=did, list_uri=list_uri, user_to_add_did=user_did)
                print(f"Added {user_did} for {did_to_handle[user_did]}")
            else:
                print(f"Would have added {user_did} for {did_to_handle[user_did]}")

    print("-" * 80)

    remainder = list(itertools.islice(to_add_dids, len(source_list)))
    if len(remainder) > 0:
        print(f"{len(remainder)} users from the original list were not added, try again with an additional SP url")
    else:
        print("Done adding")

    print("-" * 80)

    # removals, doesn't actually remove and just outputs them for later manual use
    to_remove_dids = list(already_present_dids - set(source_list_dids))
    if len(to_remove_dids) > 0:
        to_remove_profiles = client.get_profiles(to_remove_dids)
        for user in to_remove_profiles.profiles:
            profile_url = f"https://bsky.app/profile/{user.handle}"
            print(json.dumps({"display_name" : user.display_name, "handle" : user.handle, "bio" : user.description, "profile_link" : profile_url, "did" : user.did}, ensure_ascii=False))
    else:
        print("No one to remove")