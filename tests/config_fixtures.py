"""Synthetic deployments used by inherited core tests, never live-node defaults."""
from local_hand.config import PROFILE_SCHEMA, TRANSPORT_SCHEMA


def transport(branch="fixture/mailbox-v1", remote="git@example.invalid:fixtures/mailbox.git"):
    return {"schema_version":TRANSPORT_SCHEMA,"remote_url":remote,"allowed_remote_urls":[remote],"branch":branch}


def profile_v2(value):
    value["profile_schema"]=PROFILE_SCHEMA
    value["transport_policy"]=transport()
    return value
