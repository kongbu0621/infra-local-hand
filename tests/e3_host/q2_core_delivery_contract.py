"""Closed-A constants and strict records for the one-shot core acceptance delivery.

This module is deliberately side-effect free.  It is shared by the offline
packager, the local carrier client and their tests, but is not an alternate
field entry point.  The three field blobs are self-contained because no code
may be imported before their enclosing package has been completely verified.
"""
from __future__ import annotations

import hashlib
import json
import copy
from pathlib import PurePosixPath
import re


class ContractError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ContractError(code)


SCOPE = "LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1"
RULE = {
    "commit": "10d2a5c827964989f41ca6e8eeac3d44de6d0f04",
    "source_sha256": "c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5",
}
BASELINE = {
    "commit": "74366b3fe41e675b1aa2d677228714a5606c275c",
    "tree": "7df4fd0c876df13af4ec73c6f910272a72d7ea4d",
    "documents_sha256": {
        "docs/a2-execution/Q2_CORE_LIVE_INPUT_REVIEW_20261003.md":
            "39853b72755e4737b5329856691e1f616cfd2ffdf403d1c06cbeccff89686f1c",
        "docs/a2-execution/q2-core-acceptance-delivery/ARCHITECTURE.md":
            "7599870a39f04a68a84992dbc2f3035ba202963fc1cc688914f9b5fa596b54ab",
        "docs/a2-execution/q2-core-acceptance-delivery/IMPLEMENTATION_PLAN.md":
            "dd128597f90cfdf38d4a9f716fa53fd12acbb12cbc86c261f3f9c760477938c1",
        "docs/a2-execution/q2-core-acceptance-delivery/REQUIREMENTS.md":
            "8ef192452302ae2c2c55c38dd6889a0a62265404f4baa823be097f0a2524ce76",
    },
}
OWNER_DECISION = {
    "event": "LH-Q2-CORE-ACCEPTANCE-DELIVERY-CLOSURE-20261003-01",
    "record_path": "docs/governance/Q2_CORE_ACCEPTANCE_DELIVERY_OWNER_DECISION.md",
    "record_sha256": "e6a810ac5a76c903c687b6487ac2a4b08e02022fcf90927f7a34993dedb695cb",
}
CLOSURE = {
    "commit": "a8dd077392ebb656770c8f94ca3b051e93fc296d",
    "tree": "b0d651ea5cbc2c408bb43ce6f3cdc5becd5170c6",
}
AMENDMENT_SCOPE = "LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-v1"
AMENDMENT_BASELINE = {
    "commit": "0bdb49cae5586be60a7ba31d4a8e8367854d1e8c",
    "tree": "ee15aa4fa26fd2e87b40f6fad72828265e5cf9bc",
    "documents_sha256": {
        "docs/a2-execution/q2-core-binding-finalization-amendment/REQUIREMENTS.md":
            "e6b29c45c550f2ae8b3eaa91baad8d1382851dec6a69e2f807cce9233b14cdb1",
        "docs/a2-execution/q2-core-binding-finalization-amendment/ARCHITECTURE.md":
            "7782e2fb89a28052978d3ce205278906b92752e3ba1add9cd634c0e7c0f92c96",
        "docs/a2-execution/q2-core-binding-finalization-amendment/IMPLEMENTATION_PLAN.md":
            "52faaf002d9b5b9d88aef0b6f568e8ed56d2aa49eb0ea41e7eeb85d2d0b64cce",
    },
}
AMENDMENT_OWNER_DECISION = {
    "event": "LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-CLOSURE-20261004-01",
    "record_path": "docs/governance/Q2_CORE_BINDING_FINALIZATION_AMENDMENT_OWNER_DECISION.md",
    "record_sha256": "800f01b3e7d4aeec77095bbc67196837427a7dbece7f1212bca266adb3d9ddbd",
}
AMENDMENT_CLOSURE = {
    "commit": "7598886e15ed6911fe0e09e2f8d66203455f9057",
    "tree": "7f2178942c126f883829a139b842cfc2c2e12159",
}
# Offline lineage only: the wire amendment continues to name its original A/B/C.
WRITER_TRANSPORT_BASELINE = {
    "commit": "60756caedf6a2d978627272e44784d11009ac309",
    "tree": "82df6a8ec23fce903dbb09ca3feb51baacac503c",
    "documents_sha256": {
        "docs/a2-execution/q2-core-writer-transport/REQUIREMENTS.md":
            "8d2f0dcc113eaab0fb086ef5163376e0ca5c17ab3a96fb4bcc90c1fb12a9d213",
        "docs/a2-execution/q2-core-writer-transport/ARCHITECTURE.md":
            "0327482634a6c62abde72b2bfdf8566abda90b6f0dd411fea8f15f1eda175b8f",
        "docs/a2-execution/q2-core-writer-transport/IMPLEMENTATION_PLAN.md":
            "1b0d745142929dfe6d377fad826cab2fce9a40d1fffffc583517721d8c97b109",
    },
}
WRITER_TRANSPORT_OWNER_DECISION = {
    "event": "LH-Q2-CORE-WRITER-TRANSPORT-CLOSURE-20261004-01",
    "record_path": "docs/governance/Q2_CORE_WRITER_TRANSPORT_OWNER_DECISION.md",
    "record_sha256": "f62b3fe38c6b39e9063858a6a03e5fe8285fb78f90c3a2810b2163fc28932f3a",
}
WRITER_TRANSPORT_CLOSURE = {
    "commit": "8e891e11fb6e563353013ac94c201f30a1df66c9",
    "tree": "2c2ae6e075176ca359d411c127267ea1a959ddce",
}
COMPLETION_ADJUSTMENT_BASELINE = {
    "commit": "851a1afe4e55196212aa6913e81e0722deed1032",
    "tree": "5b6c8d3a55d8d0678f2b4543f13df32016630fdd",
    "documents_sha256": {
        "docs/a2-execution/q2-core-completion-adjustment/REQUIREMENTS.md":
            "08bba40c9d9c49b2b8af3a15310597514ea61641512b5ca43c70de35f06d46d1",
        "docs/a2-execution/q2-core-completion-adjustment/ARCHITECTURE.md":
            "adc7e6be062c6b85deacc774d148bce515aa51c965b3dd31152cee4a73f1455f",
        "docs/a2-execution/q2-core-completion-adjustment/IMPLEMENTATION_PLAN.md":
            "a70d51557f034f5f0ec7e626eb6226064a4e604fd6f217267282fe524495f60c",
    },
}
COMPLETION_ADJUSTMENT_OWNER_DECISION = {
    "event": "LH-Q2-CORE-COMPLETION-ADJUSTMENT-CLOSURE-20261004-01",
    "record_path": "docs/governance/Q2_CORE_COMPLETION_ADJUSTMENT_OWNER_DECISION.md",
    "record_sha256": "0f6ec728c28ca658b4c77ab035cc42bbb57e1dbe72a1a8606e579ce08b2a1757",
}
COMPLETION_ADJUSTMENT_CLOSURE = {
    "commit": "c32799c03a32d81deec02f7492c1b71eb47b2b6d",
    "tree": "1ccf7b10f65e43f5099c17c7c7fb7e9f5e5da77b",
}
CLOUD_INIT_GRANT_BASELINE = {
    "commit": "018bdd7f09998290f536ab5a3726ccb4123dffa3",
    "tree": "a444a2398766ee4cba7e4f674a326c3a18995098",
    "documents_sha256": {
        "docs/a2-execution/q2-core-cloud-init-grant-binding/REQUIREMENTS.md":
            "2330303e9bf7dd7e19c59cac6c1e864fb8c04ad08203575b15255941837fb80a",
        "docs/a2-execution/q2-core-cloud-init-grant-binding/ARCHITECTURE.md":
            "1960ca98f717866a76c57c55c04a3df09718267d86c046abcc5209115f1c645f",
        "docs/a2-execution/q2-core-cloud-init-grant-binding/IMPLEMENTATION_PLAN.md":
            "5af1d1348a7f955c6516334f68c7926fa0154a1fe7c055fdf352f136e2f70285",
    },
}
CLOUD_INIT_GRANT_OWNER_DECISION = {
    "event": "LH-Q2-CORE-CLOUD-INIT-GRANT-BINDING-CLOSURE-20261005-01",
    "record_path": "docs/governance/Q2_CORE_CLOUD_INIT_GRANT_BINDING_OWNER_DECISION.md",
    "record_sha256": "f113a7ccfa78c6b98ec27515f75e8494cc982dbd931aba7fe93a3714950417a1",
}
CLOUD_INIT_GRANT_CLOSURE = {
    "commit": "6013436554b51576e321ec08b0de2643efd5c3bc",
    "tree": "32321531cae9f60aec274600340cf027958a2e1f",
}
NEXT_ACCEPTANCE_SCOPE = "LH-Q2-CORE-NEXT-ACCEPTANCE-v1"
NEXT_ACCEPTANCE_BASELINE = {
    "commit": "0b0f445a36232f6bcd32c395b642f9a6b259d2db",
    "tree": "c2ee02917768f4f8b6ef905b7fec0159dffd224f",
    "documents_sha256": {
        "docs/a2-execution/q2-core-next-acceptance/REQUIREMENTS.md":
            "a07ab93db9c73f777cc4d39a26c25c59f633c915cd7f53f0549580e6f059fa1e",
        "docs/a2-execution/q2-core-next-acceptance/ARCHITECTURE.md":
            "43967dac7e640b4d6d46f802cb56001b1cf53d2aea724fc28d1bd98383518685",
        "docs/a2-execution/q2-core-next-acceptance/IMPLEMENTATION_PLAN.md":
            "58b0935ab8c6fe42fc76c2d023f2b26a207796d18429df17c98b03a7dd410bfd",
    },
}
NEXT_ACCEPTANCE_OWNER_DECISION = {
    "event": "LH-Q2-CORE-NEXT-ACCEPTANCE-CLOSURE-20261005-01",
    "record_path": "docs/governance/Q2_CORE_NEXT_ACCEPTANCE_OWNER_DECISION.md",
    "record_sha256": "1d346dd8aec855aae5723b7bdb880584c37eee1e829b35cf4c2121a90822eac6",
}
NEXT_ACCEPTANCE_CLOSURE = {
    "commit": "7ac69c0bd4401812b782b75005d8b63936d90a77",
    "tree": "cb3b2b16c295a32db11854cac4eafc354c9881a0",
}
HOST_CAPACITY_BOUNDARY_SCOPE = "LH-Q2-CORE-HOST-CAPACITY-BOUNDARY-v1"
HOST_CAPACITY_BOUNDARY_BASELINE = {
    "commit": "f491b15514ed0e05f7e1924785a3f7d162dae90f",
    "tree": "318a7ddb656c9256ab4348379dcb12848ef82351",
    "documents_sha256": {
        "docs/a2-execution/q2-core-host-capacity-boundary/REQUIREMENTS.md":
            "88e0b216a238eab35dd8e04f82ac194f49a9e587739d0d1cae29182b599c9924",
        "docs/a2-execution/q2-core-host-capacity-boundary/ARCHITECTURE.md":
            "fbe274526b6058c683103256ecb6b57dee8fd360321972f3bef0acd601687353",
        "docs/a2-execution/q2-core-host-capacity-boundary/IMPLEMENTATION_PLAN.md":
            "5851022f390b2b21a06a9d8fef60dae2aaa4c24fe242ce2bb81f769de36b8704",
    },
}
HOST_CAPACITY_BOUNDARY_OWNER_DECISION = {
    "event": "LH-Q2-CORE-HOST-CAPACITY-BOUNDARY-CLOSURE-20261005-01",
    "record_path": "docs/governance/Q2_CORE_HOST_CAPACITY_BOUNDARY_OWNER_DECISION.md",
    "record_sha256": "43f65857e7a2d0ae9c26b535a09c3e02c5cc091e3207790a08e7a8f61900cc3e",
}
HOST_CAPACITY_BOUNDARY_CLOSURE = {
    "commit": "434c6a07f7a84f26d7bd01de138125debc467dd4",
    "tree": "6dde47b33564d50d7d7c44b2be27529ef7bc02fb",
}
POST_SUDO_SCOPE = "LH-Q2-CORE-POST-SUDO-ACCEPTANCE-v1"
POST_SUDO_BASELINE = {
    "commit": "f9ba6fbc2fa983c46322a00f3385af172fed7cb4",
    "tree": "45b9d9dff11e87a8c83453bdab5d93c0b1ab5734",
    "documents_sha256": {
        "docs/a2-execution/q2-core-post-sudo-acceptance/REQUIREMENTS.md":
            "40430bf96501bcf738bb3137a509ce8600844398d442ed5906764646151c34ab",
        "docs/a2-execution/q2-core-post-sudo-acceptance/ARCHITECTURE.md":
            "1470cba64730bdfdfc6db806fe8ad1e0cf5f2e12c2af3f3bfdfd2c9fe40f8ae4",
        "docs/a2-execution/q2-core-post-sudo-acceptance/IMPLEMENTATION_PLAN.md":
            "63138edbba669c7d2ea111f7ad8041aa2e30b039c7d730ecea15d45a3f37bb1d",
    },
}
POST_SUDO_OWNER_DECISION = {
    "event": "LH-Q2-CORE-POST-SUDO-ACCEPTANCE-CLOSURE-20261005-01",
    "record_path": "docs/governance/Q2_CORE_POST_SUDO_ACCEPTANCE_OWNER_DECISION.md",
    "record_sha256": "b3fe02c7179bdc668d9fa16988e2f01c4dd8f5a99e25095c444e69202373c400",
}
POST_SUDO_CLOSURE = {
    "commit": "0c63e733b166f8f9539fd821db621b331a3ede61",
    "tree": "569083f1fe775c918983a88a963aebf810aa1d27",
}
LOCALE_GRAMMAR_BASELINE = {
    "commit": "25e8d6cb015b619d8a55b6157a9454501b1c5f2e",
    "tree": "3fe2510fd8ba012fe7a733300e1c3d8afdfca9bd",
    "documents_sha256": {
        "docs/a2-execution/q2-core-sshd-locale-grammar/REQUIREMENTS.md":
            "228983fc431418a74a4813f5e27a7f99c0993c1ba0199f15d721f2868c7ebc7d",
        "docs/a2-execution/q2-core-sshd-locale-grammar/ARCHITECTURE.md":
            "0c003aae0578064e72486c44c517fcd55b97701a1d7de1b826f22802703a2eab",
        "docs/a2-execution/q2-core-sshd-locale-grammar/IMPLEMENTATION_PLAN.md":
            "fc23b1ed7a6be70f438bdd3c07fbd7534c615626a7a0abfd862ab9239cfeb4d6",
    },
}
LOCALE_GRAMMAR_OWNER_DECISION = {
    "event": "LH-Q2-CORE-SSHD-LOCALE-GRAMMAR-CLOSURE-20261005-01",
    "record_path": "docs/governance/Q2_CORE_SSHD_LOCALE_GRAMMAR_OWNER_DECISION.md",
    "record_sha256": "da2ab72e85fa2264505364470a4a59f164ecc00899f7f608e32387a11c755cb5",
}
LOCALE_GRAMMAR_CLOSURE = {
    "commit": "86c5779f306d24756a8be383846e55afc0708b8b",
    "tree": "168e989cdd4b9c243531a037fbeeaf11cfa82042",
}
POST_LOCALE_SCOPE = "LH-Q2-CORE-POST-LOCALE-ACCEPTANCE-v1"
POST_LOCALE_BASELINE = {
    "commit": "a243362d473891469b012a0ab8c3bd221794aa50",
    "tree": "179045d0c3bcf9bf6c154c191068c96c379fe13e",
    "documents_sha256": {
        "docs/a2-execution/q2-core-post-locale-acceptance/REQUIREMENTS.md":
            "35292af3218df0666b8c37251d802b0b3d68616ad07c4b36899d9c02d1169389",
        "docs/a2-execution/q2-core-post-locale-acceptance/ARCHITECTURE.md":
            "ae4aa9731e797ee79982e03f62489ec5a02d439b12de488279ba5c960ef16bcc",
        "docs/a2-execution/q2-core-post-locale-acceptance/IMPLEMENTATION_PLAN.md":
            "868d173d855e80be3d81218cf882febb5e00576e1d0505d539bade8fef99e870",
    },
}
POST_LOCALE_OWNER_DECISION = {
    "event": "LH-Q2-CORE-POST-LOCALE-ACCEPTANCE-CLOSURE-20261005-01",
    "record_path": "docs/governance/Q2_CORE_POST_LOCALE_ACCEPTANCE_OWNER_DECISION.md",
    "record_sha256": "87ea9b65f33794a422d0387bde700dfe1b1730b5a819485381473031f5bb036b",
}
POST_LOCALE_CLOSURE = {
    "commit": "fe635c4885b8f31dd13901bef47e619480b2eda3",
    "tree": "e72aa24f0ec039730bcb75f2ccafc1eb0145b948",
}
MINIMAL_SCOPE = "LH-Q2-CORE-MINIMAL-CONTINUATION-v1"
MINIMAL_BASELINE = {
    "commit": "5d6cefa602e9146f02887ebfaa4b0cad4e376ff2",
    "tree": "72262d27c2caef48db0965989508b1f193f3b527",
    "documents_sha256": {
        "docs/a2-execution/q2-core-minimal-continuation/REQUIREMENTS.md":
            "f132068c02f6a49332e991525591c409d38690bb1cbff51d0f17de1e68e28769",
        "docs/a2-execution/q2-core-minimal-continuation/ARCHITECTURE.md":
            "121f67c11bbc85e18aed7635f3541cdb581fdb52aceba25fb12aca18aecf760b",
        "docs/a2-execution/q2-core-minimal-continuation/IMPLEMENTATION_PLAN.md":
            "093e0daac0f85cc78a48fcf58386d3133cfc796e9faba416b622dd0e072b8c58",
    },
}
MINIMAL_OWNER_DECISION = {
    "event": "LH-Q2-CORE-MINIMAL-CONTINUATION-CLOSURE-20261007-01",
    "record_path": "docs/governance/Q2_CORE_MINIMAL_CONTINUATION_OWNER_DECISION.md",
    "record_sha256": "3c82fd76fc6e8395a91ef9d93b62cd72ae14207100e66fbf73358ac2bf987bdd",
}
MINIMAL_CLOSURE = {
    "commit": "8a4c24cefe4abbab193577b2dff48fc49626cae4",
    "tree": "afbdd25b2a25d961dcd79587579c1796b3263e24",
}
SERIAL_SCOPE = "LH-Q2-CORE-SERIAL-CONTINUATION-v1"
SERIAL_BASELINE = {
    "commit": "7869bbcaeb1dad3a1736131a3ff2e225ddf5e7cc",
    "tree": "bc6bee8c650fbcf412e0fbf49f7d3c16c62da1c5",
    "documents_sha256": {
        "docs/a2-execution/q2-core-serial-continuation/REQUIREMENTS.md":
            "39c77516b6d7f54c01fe96775e7c12d56d764daff58d3c69453e97436e993c3f",
        "docs/a2-execution/q2-core-serial-continuation/ARCHITECTURE.md":
            "293239f014bc3f5f377ce18e555ef56b9b048116a2bd40bcf382d8f67a055e5b",
        "docs/a2-execution/q2-core-serial-continuation/IMPLEMENTATION_PLAN.md":
            "52e63872aca00b2027dae7d4d44d06a9bcac49dd389c455bd264960340754b89",
    },
}
SERIAL_OWNER_DECISION = {
    "event": "LH-Q2-CORE-SERIAL-CONTINUATION-CLOSURE-20261007-01",
    "record_path": "docs/governance/Q2_CORE_SERIAL_CONTINUATION_OWNER_DECISION.md",
    "record_sha256": "9b5eed75b3153b980f1e3874f298aa65272b1129b77e2cc43fecb9409661c7a4",
}
SERIAL_CLOSURE = {
    "commit": "91c706b52dbc70498d5d872f59874c002cef23db",
    "tree": "0a3008294aca7bb70d6fca883b681b813dc12165",
}
SYSTEMCTL_SCOPE = "LH-Q2-CORE-SYSTEMCTL-CONTINUATION-v1"
SYSTEMCTL_BASELINE = {'commit': '62666eeec9f2f28833876df3d68ce6e8b8e0af54',
 'tree': '52ebb86280484d16e51aa40aca32f43cfceb4458',
 'documents_sha256': {'docs/a2-execution/q2-core-systemctl-continuation/ARCHITECTURE.md': 'ba25e87046caf0ccadbb8792fe8b8390d4df891a88bbd95e93ad48799be5fcb5',
                      'docs/a2-execution/q2-core-systemctl-continuation/IMPLEMENTATION_PLAN.md': 'b69186abe3daf2cb9d7457750c15b2f9d4781e2cdc328bab6b1d0c949c87ef6b',
                      'docs/a2-execution/q2-core-systemctl-continuation/REQUIREMENTS.md': '2656889d68132bf0698c03f1aff77842be7255fa8c7dd5876070029e78f0d5ee'}}
SYSTEMCTL_OWNER_DECISION = {'event': 'LH-Q2-CORE-SYSTEMCTL-CONTINUATION-CLOSURE-20261007-01',
 'record_path': 'docs/governance/Q2_CORE_SYSTEMCTL_CONTINUATION_OWNER_DECISION.md',
 'record_sha256': '29e63c791de507cda1e48f2e89a992783a9fe6866850d006ce6a36abcb39c8ac'}
SYSTEMCTL_CLOSURE = {'commit': '7b342ced547639f93797e849b34ed3da4915c8d3',
 'tree': 'ec1ed26d198c9226816ff00de6896eb3d7e102de'}
TEMPLATE_SCOPE = "LH-Q2-CORE-TEMPLATE-CONTINUATION-v1"
TEMPLATE_BASELINE = {
    "commit": "80c7c8eaeda0853317c679b31b0ed1f1ac13e49b",
    "tree": "68983c68d936d0e03ef90dd22c656e7cb41079cc",
    "documents_sha256": {
        "docs/a2-execution/q2-core-template-continuation/REQUIREMENTS.md": "e960f2639f22d82bf8acebb917ee7e180382c2ae64cb1d74b2b21f7419cfcb9d",
        "docs/a2-execution/q2-core-template-continuation/ARCHITECTURE.md": "8e93e92c527884e6845478544a0d3507fc34e1917fc94593320752e5f800743f",
        "docs/a2-execution/q2-core-template-continuation/IMPLEMENTATION_PLAN.md": "73f2889af1c50ef787479a2f257db2089171812201f31aa4fc55de7a229fa509",
    },
}
TEMPLATE_OWNER_DECISION = {
    "event": "LH-Q2-CORE-TEMPLATE-CONTINUATION-CLOSURE-20261008-01",
    "record_path": "docs/governance/Q2_CORE_TEMPLATE_CONTINUATION_OWNER_DECISION.md",
    "record_sha256": "05ce90722d4504951440dd1776a4b9ba194168553698eb179f8d33db3b3b6e2e",
}
TEMPLATE_CLOSURE = {
    "commit": "bb9b3c6e9b397121220c22515e4ef637d12c7297",
    "tree": "d1e7261208ae8093971b6b127c1095c2e45b1b80",
}
NAMES_SCOPE = "LH-Q2-CORE-NAMES-CONTINUATION-v1"
NAMES_BASELINE = {
    "commit": "68cae882e3b831aaa191e7a877278ccf6ba10e2b",
    "tree": "af1df36d31326ae041fd60f7c77499673aeb0cf9",
    "documents_sha256": {
        "docs/a2-execution/q2-core-names-continuation/REQUIREMENTS.md": "52fad6aec854cdce4031deb09feabf16fdb393c5f3a1e45fb43230afd12a320f",
        "docs/a2-execution/q2-core-names-continuation/ARCHITECTURE.md": "27883a8b69500fcdfa87e4b865faace1aac8849b5acc9802409fece28a4af4db",
        "docs/a2-execution/q2-core-names-continuation/IMPLEMENTATION_PLAN.md": "a24b97894fbdcd29da8228076ccedf5afc1cb2906e12ff70aa8d58c06a803a06",
    },
}
NAMES_OWNER_DECISION = {
    "event": "LH-Q2-CORE-NAMES-CONTINUATION-CLOSURE-20261008-01",
    "record_path": "docs/governance/Q2_CORE_NAMES_CONTINUATION_OWNER_DECISION.md",
    "record_sha256": "b49d8d77bcd83d125fc143eb345cb8fc733002f73f5c2c1f78556ed039e5408b",
}
NAMES_CLOSURE = {
    "commit": "eba5023b13e42d4610533b7e7c4eede3ebd658db",
    "tree": "0cd836080ff9d5957e9eeac7c38c8e884109d26d",
}
EXEC_SCOPE = "LH-Q2-CORE-EXEC-CONTINUATION-v1"
EXEC_BASELINE = {
    "commit": "5b14123206ced8117374d3fd2ef84b9f38784db3",
    "tree": "74e55d39aea86775407b566487c5a108a2b42439",
    "documents_sha256": {
        "docs/a2-execution/q2-core-exec-continuation/REQUIREMENTS.md": "9026fc7b74fc9ffb4c04a18d3450d705ee5c6c39e10a70337cba67efa69b4e59",
        "docs/a2-execution/q2-core-exec-continuation/ARCHITECTURE.md": "84f203d282471c94c348ace32b5269de0521a51a9881cff9dabff97dde820128",
        "docs/a2-execution/q2-core-exec-continuation/IMPLEMENTATION_PLAN.md": "601e3e8c35a8f2363adc1462e0e4092e07b5b46e917ba4b27db34ba32cf650ca",
    },
}
EXEC_OWNER_DECISION = {
    "event": "LH-Q2-CORE-EXEC-CONTINUATION-CLOSURE-20261008-01",
    "record_path": "docs/governance/Q2_CORE_EXEC_CONTINUATION_OWNER_DECISION.md",
    "record_sha256": "39f64e1ea1c4fe4c11535abcb0847b32b8911d191a7c735390595e9ae29a78e8",
}
EXEC_CLOSURE = {
    "commit": "987c77f6eb16e7ca41d8b1d4ccd7f89faf418d32",
    "tree": "7d24f3cae840a242b39bd796d3ae024570766a29",
}
GS_SCOPE = "LH-Q2-CORE-GUEST-STARTUP-CONTINUATION-v1"
GS_BASELINE = {
    "commit": "7ea9aed6a4f8be6d6fee0ee549e1e02378f32672",
    "tree": "87af0b77a932330f0399d4df4ebf2ddfd2c83bf9",
    "documents_sha256": {
        "docs/a2-execution/q2-core-guest-startup-continuation/REQUIREMENTS.md": "8e02859996b1daa22098e4ee21c1747b9d4a7f6c6f95d43a920f72d113ff3476",
        "docs/a2-execution/q2-core-guest-startup-continuation/ARCHITECTURE.md": "87f9a21a8b56444fade0bde6750425a71c3a4a1d6274f739fcdc1178ca7e1fa7",
        "docs/a2-execution/q2-core-guest-startup-continuation/IMPLEMENTATION_PLAN.md": "fb6ed0428afc386ced7bd1e7e09f8f1bb08710967a2dbbd585713135797fbbe0"
    }
}
GS_OWNER_DECISION = {
    "event": "LH-Q2-CORE-GUEST-STARTUP-CONTINUATION-CLOSURE-20261008-01",
    "record_path": "docs/governance/Q2_CORE_GUEST_STARTUP_CONTINUATION_OWNER_DECISION.md",
    "record_sha256": "461d8f7458979786e4a267186fda0ebc07ca2d79e2c020bd9f6891d4af48a98f"
}
GS_CLOSURE = {
    "commit": "001bd4f7baedf115ce67feba87a21d8e259c8d1d",
    "tree": "57940587f04c3fd2e1fe991c2b0e290aa66d11e6"
}
QI_SCOPE = "LH-Q2-CORE-Q1-BINDING-CONTINUATION-v1"
QI_BASELINE = {'commit': 'e66b1b5524f22d60c810dffac59ca418c5ad4236', 'tree': '21d63b7e40a5e3017b1a35fe159e90fd50bdf712', 'documents_sha256': {'docs/a2-execution/q2-core-q1-binding-continuation/REQUIREMENTS.md': '2c5181ab5a633d9e4b0af824aace9aada6f1679c0cbf0977bcb23004b53ad3dd', 'docs/a2-execution/q2-core-q1-binding-continuation/ARCHITECTURE.md': '2938f0e7b77cbc317093f897f3b8e84074340cbd7f3a1e622d4485d458ddfa49', 'docs/a2-execution/q2-core-q1-binding-continuation/IMPLEMENTATION_PLAN.md': 'fc4a3dc39d9830116f6c4dd881523fb84c8c4b7b81f730203733ca3d61a923f7'}}
QI_OWNER_DECISION = {'event': 'LH-Q2-CORE-Q1-BINDING-CONTINUATION-CLOSURE-20261008-01', 'record_path': 'docs/governance/Q2_CORE_Q1_BINDING_CONTINUATION_OWNER_DECISION.md', 'record_sha256': '55a87331d7648c83779a8796d5c2e3799e651534a3b91fa4e104b6fb57bd4c93'}
QI_CLOSURE = {'commit': '61fae1da528105605a023f260130c4e0d9c1bc02', 'tree': '88a6d363fe62817dac807e9f279730fa955dec35'}
DS_SCOPE = "LH-Q2-CORE-DECLARED-STARTUP-CONTINUATION-v1"
DS_BASELINE = {'commit': '2b13dd653ca19eaaf46a18e6ffc3f447b62eee59', 'tree': 'c686e5dbf5454f682603f9b7575cc4292402be34', 'documents_sha256': {'docs/a2-execution/q2-core-declared-startup-continuation/REQUIREMENTS.md': '4ae983f96c2a3e25ebf435b8db2af9abc487c570702a4f8bd7614dc7ac5eb392', 'docs/a2-execution/q2-core-declared-startup-continuation/ARCHITECTURE.md': '61b543eb04810047e9a0f9e0fbeab032de6943792b9e3ca5d4653393da147942', 'docs/a2-execution/q2-core-declared-startup-continuation/IMPLEMENTATION_PLAN.md': '965f841919a015e0f6e6212807fe710c45be21c51b134451d92fe199123e678a'}}
DS_OWNER_DECISION = {'event': 'LH-Q2-CORE-DECLARED-STARTUP-CONTINUATION-CLOSURE-20261009-01', 'record_path': 'docs/governance/Q2_CORE_DECLARED_STARTUP_CONTINUATION_OWNER_DECISION.md', 'record_sha256': 'ec54f363906547a7ee474832eeaa28fd6855a817a7c52e03ae8fd34b4919deaf'}
DS_CLOSURE = {'commit': 'a2a6d62de08b2d1d8fbf9da97e8ccf938e3777c1', 'tree': 'a9c54bbfe24fefa8e8408846ebaf532a191e237f'}

LOCALE_REPAIR = "d0c8749e47647264c14c406cd85c8c68006689a0"
CANDIDATE = {
    "commit": "4b6e4a7c403362358192086b88679e1326dcb2e1",
    "tree": "4d4349580c9f4b67cc26f601126849c2bc8d76a4",
}
CANDIDATE_PARENT = "607100a57206f7dc7cfcbd6cae8507cfa599b813"
WHEEL = {
    "basename": "infra_local_hand-0.2.0a1-py3-none-any.whl",
    "bytes": 288375,
    "sha256": "ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9",
    "payload_digest": "b4d094a9f70c308c63870c9fbf273b6b0646ad211d6f61a79901f52e67cf2e23",
}
PROJECTION = {
    "basename": ".local-hand-source-projection.json",
    "bytes": 11811,
    "sha256": "55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d",
    "file_count": 89,
}

SESSION_ID = "lhqcore-20261007a"
INSTALL_BASENAME = "local-hand-core-acceptance-20261007a"
STAGING_BASENAME = ".local-hand-core-acceptance-20261007a.staging"
INSTALL_UUID = "452e2905-1442-4b89-988c-50eefcbd3a09"
CARRIER_UNIT = "lhqcore20261007a-carrier.service"
MARKER_BASENAME = ".lhqcore-20261007a.carrier-consumed.json"
OUTPUT_BASENAMES = {
    "stdout_basename": ".lhqcore-20261007a.stdout",
    "stderr_basename": ".lhqcore-20261007a.stderr",
    "remote_result_basename": ".lhqcore-20261007a.remote-result.json",
    "capture_manifest_basename": ".lhqcore-20261007a.capture-manifest.json",
    "local_receipt_basename": ".lhqcore-20261007a.acceptance-receipt.json",
}

PACKAGE_MAGIC = b"LHCFP1\n"
HELLO_MAGIC = b"LHCHLO1\n"
BIND_MAGIC = b"LHCBND1\n"
OUTPUT_MAGIC = b"LHCOUT1\n"
PACKAGE_SCHEMA = "local-hand-q2-core-field-package/v3"
LOCATORS_SCHEMA = "local-hand-q2-core-private-locators/v1"
LOCATOR_RELATION_SCHEMA = "local-hand-q2-core-locator-relation/v2"
CONSUMPTION_SCHEMA = "local-hand-q2-core-carrier-consumption/v2"
HELLO_SCHEMA = "local-hand-q2-core-carrier-hello/v2"
SESSION_SCHEMA = "local-hand-q2-core-dispatch-session/v2"
APPROVED_INPUTS_SCHEMA = "local-hand-q2-core-approved-inputs/v1"
APPROVED_INPUTS_PATH = "private/approved-inputs.json"
APPROVED_INPUTS_LIMIT = 2097152
CARRIER_ARGV_SCHEMA = "local-hand-q2-core-carrier-argv/v1"
MANAGEMENT_BINDING_SCHEMA = "local-hand-q2-core-local-management-binding/v1"
LOCAL_WRITER_SCHEMA = "local-hand-q2-core-local-writer/v1"
TRUTH_EVIDENCE_SCHEMA = "local-hand-q2-core-local-truth-evidence/v1"
PREPARATION_INPUT_SCHEMA = "local-hand-q2-core-preparation-input/v1"
REMOTE_RESULT_SCHEMA = "local-hand-q2-core-remote-result/v2"
RESOURCE_ACCOUNTING_SCHEMA = "local-hand-q2-core-resource-accounting/v1"

PACKAGE_LIMITS = {
    "package_bytes": 67100656,
    "manifest_bytes": 2097152,
    "members": 8192,
    "member_bytes": 33554432,
    "shared_allocated_bytes": 134217728,
    "shared_entries": 8192,
    "carrier_audit_bytes": 16777216,
    "carrier_audit_inodes": 1024,
    "carrier_output_bytes": 125829120,
}
LIMITS = {
    "carrier_seconds": 1800,
    "remote_unit_seconds": 1600,
    "guest_duration_cap_seconds": 1500,
    "preparation_seconds": 300,
    "owner_seconds": 240,
    "case_gate_seconds": 630,
    "hello_frame_bytes": 8208,
    "bind_frame_bytes": 8208,
    "package_bytes": 67100656,
    "carrier_input_bytes": 67108864,
    "output_package_bytes": 117432304,
    "carrier_stderr_bytes": 8388608,
    "carrier_output_bytes": 125829120,
    "host_capture_bytes": 134217728,
    "host_capture_inodes": 32,
    "carrier_cpu_seconds": 1600,
    "carrier_memory_bytes": 2147483648,
    "carrier_pids": 256,
    "carrier_audit_bytes": 16777216,
    "carrier_audit_inodes": 1024,
    "shared_bytes": 134217728,
    "shared_inodes": 8192,
    "case_physical_bytes": 75497472,
    "case_physical_inodes": 5888,
    "all_case_physical_bytes": 226492416,
    "all_case_physical_inodes": 17664,
    "case_admission_bytes": 142606336,
    "case_admission_inodes": 7936,
    "all_case_admission_bytes": 427819008,
    "all_case_admission_inodes": 23808,
    "all_case_cpu_seconds": 2580,
    "total_cpu_seconds": 4180,
    "all_case_output_bytes": 100663296,
    "peak_memory_bytes": 5502926848,
    "peak_pids": 2320,
    "job_units": 15,
    "controller_units": 6,
    "quota_query_units": 5,
    "dynamic_quota_units": 15,
    "native_children": 16,
    "total_guest_physical_bytes": 377487360,
    "total_guest_physical_inodes": 26880,
    "total_guest_admission_bytes": 578813952,
    "total_guest_admission_inodes": 33024,
}

DIRECTORY_ROLES = (
    "reservation", "state", "authority", "journal", "capture", "declarations",
    "session", "control", "profile_work", "profile_evidence", "profile_temporary",
    "store_parent",
)
ROOT_REFS = (
    "work-a", "evidence-a", "temporary-a", "work-b", "evidence-b", "temporary-b",
    "retained_store",
)
CASES = (
    {
        "index": 1, "case_id": "c01-h01-normal", "kind": "H01_NORMAL", "predecessor": None,
        "preparation_id": "lhqc07a01h01normal", "operation_id": "9d68ffce-3e53-4933-8643-dc65e48d9ba2",
        "controller_prefix": "lhqcore20261007a-c01", "project_ids": list(range(12501, 12508)),
        "phases": ["preflight", "business", "evidence"],
    },
    {
        "index": 2, "case_id": "c02-q4-cancel", "kind": "Q4_HELPER_RUNNING_CANCEL_SUBSET",
        "predecessor": "c01-h01-normal", "preparation_id": "lhqc07a02q4cancel",
        "operation_id": "a214d2c1-f3d4-4c72-b01a-e0446626dedf",
        "controller_prefix": "lhqcore20261007a-c02", "project_ids": list(range(12508, 12515)),
        "phases": ["preflight"],
    },
    {
        "index": 3, "case_id": "c03-h11-recovery", "kind": "H11_SAME_LEDGER_RECOVERY",
        "predecessor": "c02-q4-cancel", "preparation_id": "lhqc07a03h11recovery",
        "operation_id": "bd223507-1240-456f-82e0-0ae12e0a50ea",
        "controller_prefix": "lhqcore20261007a-c03", "project_ids": list(range(12515, 12522)),
        "phases": ["preflight"],
    },
)

SCHEMA_FIELDS = {
    HELLO_SCHEMA: (
        "schema", "scope", "loader_sha256", "bootstrap_sha256", "guest_boot_id",
        "guest_boottime_origin_ns", "guest_monotonic_origin_ns", "pid", "uid", "gid",
        "euid", "egid", "python", "carrier_unit", "process_limits", "remote_management",
    ),
    "local-hand-q2-core-carrier-bind/v1": (
        "schema", "scope", "session_id", "hello_sha256", "consumption_sha256",
        "package_basename", "package_bytes", "package_sha256", "host_boottime_origin_ns",
        "host_monotonic_origin_ns", "host_boottime_deadline_ns", "host_monotonic_deadline_ns",
        "host_boottime_bind_ns", "host_monotonic_bind_ns", "host_remaining_floor_ns",
        "clock_margin_ns", "local_final_reserve_ns", "mapped_duration_ns",
        "guest_duration_cap_ns", "guest_duration_ns",
    ),
    SESSION_SCHEMA: (
        "schema", "scope", "rule", "baseline", "owner_decision", "closure",
        "implementation", "amendment", "package", "entry", "locators", "consumption", "session_id",
        "outer", "admission", "installation", "output", "limits", "cases", "state",
    ),
    "local-hand-q2-core-case-intent/v1": (
        "schema", "session_id", "index", "case_id", "kind", "predecessor",
        "preparation_id", "identity", "operation_id", "controller_prefix", "project_ids",
        "directory_roles", "planned_directories", "planned_roots", "preparation_input_sha256",
        "phases", "budgets", "state",
    ),
    "local-hand-q2-core-case-plan/v1": (
        "schema", "session_id", "index", "case_id", "kind", "predecessor",
        "preparation_id", "identity", "principal", "authority_path", "ledger_path", "request",
        "operation_id", "roots", "controllers", "system_geometry", "phases",
        "empty_ledger_expectation", "deadlines", "budgets",
    ),
    "local-hand-q2-core-phase-receipt/v1": (
        "schema", "session_id", "index", "case_id", "phase", "quota_request_id",
        "quota_request_sha256", "query_unit", "listener_unit", "admission_unit",
        "budget_deadline_ns", "phase_deadline_ns", "stage_deadline_ns",
        "controller_deadline_ns", "source_artifacts", "source_artifacts_sha256",
    ),
    "local-hand-q2-core-empty-ledger-gate/v1": (
        "schema", "session_id", "index", "case_id", "ledger_path", "dev", "ino",
        "authority_id", "ledger_id", "snapshot_sha256", "operations", "events", "leases",
        "sidecars", "checked_boottime_ns", "stage", "before_submit",
    ),
    "local-hand-q2-core-ledger-export/v1": (
        "schema", "session_id", "index", "case_id", "authority_id", "ledger_id",
        "operation_id", "ledger_identity", "operation", "events", "sidecars",
        "exported_boottime_ns",
    ),
    "local-hand-q2-core-case-verdict/v1": (
        "schema", "session_id", "index", "case_id", "status", "semantic_pass",
        "observations", "artifacts", "missing", "stop",
    ),
    "local-hand-q2-core-h11-recovery-proof/v1": (
        "schema", "session_id", "index", "case_id", "candidate", "ledger_identity",
        "recovery_plan", "recovery_summary", "launcher_result", "gateway_snapshot",
        "origin_capture", "control_seal", "result_identity", "assertions",
    ),
    "local-hand-q2-core-remote-result/v1": (
        "schema", "session_id", "consumption_sha256", "state", "cases",
        "h01_business_execution", "h01_result_package", "usage", "missing",
    ),
    REMOTE_RESULT_SCHEMA: (
        "schema", "session_id", "consumption_sha256", "state", "cases",
        "h01_business_execution", "h01_result_package", "usage", "missing", "resource_accounting",
    ),
    "local-hand-q2-core-output-package/v1": (
        "schema", "session_id", "remote_result", "cases", "members", "limits",
    ),
    "local-hand-q2-core-capture-manifest/v1": (
        "schema", "session_id", "consumption_sha256", "stdout", "stderr",
        "output_package", "wait", "files", "logical_bytes", "allocated_bytes", "inodes",
        "fsync_complete", "reread_equal", "missing",
    ),
    "local-hand-q2-core-local-acceptance-receipt/v1": (
        "schema", "scope", "session_id", "consumption", "transport", "remote_result",
        "wait", "capture", "real_task_execution", "result_evidence_collection", "state",
        "missing",
    ),
    CONSUMPTION_SCHEMA: (
        "schema", "scope", "session_id", "baseline", "owner_decision", "closure",
        "implementation", "amendment", "candidate", "package", "approved_inputs_sha256",
        "local_management_binding_sha256", "writer", "carrier_argv_sha256",
        "host_boottime_origin_ns", "host_monotonic_origin_ns", "host_boottime_deadline_ns",
        "host_monotonic_deadline_ns", "state",
    ),
    MANAGEMENT_BINDING_SCHEMA: (
        "schema", "anchor", "writer", "wrapper", "fixture_start", "fixture_cloud_config",
        "profile", "environment", "dependencies", "identity", "identity_public", "known_hosts",
        "cwd", "remote_expectation", "transport",
    ),
    LOCAL_WRITER_SCHEMA: (
        "schema", "user_namespace", "pid_namespace", "process", "uid", "gid", "supplementary_gids",
    ),
}

REMOTE_STATES = (
    "REMOTE_PREFIX_STARTED", "BOUND", "REMOTE_ADMITTED", "INSTALLED", "H01_INTENT",
    "H01_PLANNED", "H01_PASS", "Q4_INTENT", "Q4_PLANNED", "Q4_PASS", "H11_INTENT",
    "H11_PLANNED", "H11_RECOVERY_PASS", "REMOTE_FINALIZING", "REMOTE_FINALIZED",
)
LOCAL_STATES = (
    "STATIC_VERIFIED", "CARRIER_CONSUMED", "CONSUMPTION_RECORD_COMPLETE",
    "TRANSPORT_STARTED", "LOCAL_AWAITING_REMOTE", "LOCAL_FINALIZING", "COMPLETE",
)


def sha256(raw):
    require(type(raw) is bytes, "CORE_BYTES")
    return hashlib.sha256(raw).hexdigest()


def _pairs(items):
    value = {}
    for key, item in items:
        require(type(key) is str and key not in value, "CORE_JSON_DUPLICATE_KEY")
        value[key] = item
    return value


def _constant(value):
    raise ContractError("CORE_JSON_NONFINITE")


def _shape(value, depth=0, count=None):
    count = [0] if count is None else count
    count[0] += 1
    require(depth <= 32 and count[0] <= 262144, "CORE_JSON_COMPLEXITY")
    require(not isinstance(value, float), "CORE_JSON_FLOAT")
    if isinstance(value, dict):
        require(all(type(k) is str for k in value), "CORE_JSON_KEY")
        for item in value.values():
            _shape(item, depth + 1, count)
    elif isinstance(value, list):
        for item in value:
            _shape(item, depth + 1, count)
    else:
        require(value is None or type(value) in (str, int, bool), "CORE_JSON_VALUE")
    return value


def canonical(value, *, newline=False, limit=None):
    _shape(value)
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                         allow_nan=False).encode("ascii") + (b"\n" if newline else b"")
    except (TypeError, ValueError, UnicodeError) as error:
        raise ContractError("CORE_JSON_ENCODE") from error
    if limit is not None:
        require(type(limit) is int and 0 <= len(raw) <= limit, "CORE_JSON_LIMIT")
    return raw


def document(raw, *, limit, newline=False):
    require(type(raw) is bytes and 0 < len(raw) <= limit, "CORE_JSON_LIMIT")
    if newline:
        require(raw.endswith(b"\n") and not raw.endswith(b"\n\n"), "CORE_JSON_NEWLINE")
    else:
        require(not raw.endswith(b"\n"), "CORE_JSON_NEWLINE")
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs, parse_constant=_constant)
    except ContractError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ContractError("CORE_JSON_DECODE") from error
    _shape(value)
    require(canonical(value, newline=newline) == raw, "CORE_JSON_CANONICAL")
    return value


def exact(value, fields, code="CORE_FIELDS"):
    require(type(value) is dict and set(value) == set(fields), code)
    return value


def digest(value, code="CORE_DIGEST"):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, code)
    return value


def commit(value, code="CORE_COMMIT"):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) is not None, code)
    return value


def integer(value, low=0, high=2**63 - 1, code="CORE_INTEGER"):
    require(type(value) is int and low <= value <= high, code)
    return value


def relative_path(value, code="CORE_PATH"):
    require(type(value) is str and value.isascii() and 0 < len(value) <= 4096
            and re.fullmatch(r"[A-Za-z0-9._/-]+", value) is not None
            and "//" not in value and "\\" not in value and "\0" not in value, code)
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value
            and all(part not in ("", ".", "..") for part in path.parts), code)
    return value


def validate_package_basename(value, code="CORE_BIND_PACKAGE"):
    """Match the standalone bootstrap's existing single-file BIND name."""
    relative_path(value, code)
    require(re.fullmatch(r"[A-Za-z0-9._-]+\.lhfp", value) is not None, code)
    return value


def absolute_path(value, code="CORE_ABSOLUTE_PATH"):
    require(type(value) is str and value.isascii() and value.startswith("/")
            and not value.startswith("//") and "\\" not in value and "\0" not in value
            and len(value) <= 4096, code)
    path = PurePosixPath(value)
    require(path.as_posix() == value and ".." not in path.parts, code)
    return value


def validate_record(value, schema=None):
    require(type(value) is dict and type(value.get("schema")) is str, "CORE_RECORD")
    selected = value["schema"] if schema is None else schema
    require(value["schema"] == selected and selected in SCHEMA_FIELDS, "CORE_SCHEMA")
    exact(value, SCHEMA_FIELDS[selected], "CORE_RECORD_FIELDS")
    return value


def validate_amendment(value, *, implementation=None):
    """Check the frozen A/B/C chain; Git ancestry of D is checked at freeze."""
    exact(value, {"baseline", "owner_decision", "closure", "implementation"}, "CORE_AMENDMENT_FIELDS")
    require(value["baseline"] == AMENDMENT_BASELINE
            and value["owner_decision"] == AMENDMENT_OWNER_DECISION
            and value["closure"] == AMENDMENT_CLOSURE, "CORE_AMENDMENT_AUTHORITY")
    current = exact(value["implementation"], {"commit", "tree"}, "CORE_AMENDMENT_IMPLEMENTATION")
    for field in ("commit", "tree"):
        commit(current[field], "CORE_AMENDMENT_IMPLEMENTATION")
        require(current[field] != "0" * 40, "CORE_AMENDMENT_IMPLEMENTATION")
    require(current["commit"] not in {
        BASELINE["commit"], CLOSURE["commit"], AMENDMENT_BASELINE["commit"],
        AMENDMENT_CLOSURE["commit"], "520f77f578b90d31870517e33e29bee42918f3c0",
    }, "CORE_AMENDMENT_IMPLEMENTATION")
    require(implementation is None or current == implementation, "CORE_AMENDMENT_IMPLEMENTATION")
    return value


def validate_local_writer(value):
    """Validate a bound host identity; do not observe or infer current identity."""
    validate_record(value, LOCAL_WRITER_SCHEMA)
    for field in ("user_namespace", "pid_namespace"):
        namespace = exact(value[field], {"dev", "ino"}, "CORE_LOCAL_WRITER_NAMESPACE")
        integer(namespace["dev"], code="CORE_LOCAL_WRITER_NAMESPACE")
        integer(namespace["ino"], 1, code="CORE_LOCAL_WRITER_NAMESPACE")
    process = exact(value["process"], {"pid", "starttime_ticks"}, "CORE_LOCAL_WRITER_PROCESS")
    integer(process["pid"], 1, code="CORE_LOCAL_WRITER_PROCESS")
    integer(process["starttime_ticks"], code="CORE_LOCAL_WRITER_PROCESS")
    for field in ("uid", "gid"):
        identities = exact(value[field], {"real", "effective", "saved", "filesystem"},
                           "CORE_LOCAL_WRITER_CREDENTIALS")
        for item in identities.values():
            integer(item, code="CORE_LOCAL_WRITER_CREDENTIALS")
        require(len(set(identities.values())) == 1, "CORE_LOCAL_WRITER_CREDENTIALS")
    groups = value["supplementary_gids"]
    require(type(groups) is list, "CORE_LOCAL_WRITER_GROUPS")
    for item in groups:
        integer(item, code="CORE_LOCAL_WRITER_GROUPS")
    require(groups == sorted(set(groups)), "CORE_LOCAL_WRITER_GROUPS")
    canonical(value, limit=4096)
    return value


def make_amendment(implementation):
    return validate_amendment({"baseline": copy.deepcopy(AMENDMENT_BASELINE),
        "owner_decision": copy.deepcopy(AMENDMENT_OWNER_DECISION),
        "closure": copy.deepcopy(AMENDMENT_CLOSURE),
        "implementation": copy.deepcopy(implementation)})


def make_completion_adjustment(implementation):
    return {"baseline": copy.deepcopy(COMPLETION_ADJUSTMENT_BASELINE),
            "owner_decision": copy.deepcopy(COMPLETION_ADJUSTMENT_OWNER_DECISION),
            "closure": copy.deepcopy(COMPLETION_ADJUSTMENT_CLOSURE),
            "implementation": copy.deepcopy(implementation)}


def resource_pool_definitions(locators):
    """Host-side reading of approved A's fixed classification; no guest effects."""
    rows = []
    def add(name, case, amount, inodes, roots, project=None):
        rows.append(dict(pool_id=name, case_id=case, byte_limit=amount, inode_limit=inodes,
                         measurement_kind="PROJECT_QUOTA" if project else "OWNED_ALLOCATION",
                         roots=sorted(roots), project_id=project))
    def path(role, suffix):
        parent = absolute_path(locators[role + "_parent"])
        return parent + "/" + suffix, role
    add("shared_install", None, 134217728, 8192,
        [path("install", name) for name in (INSTALL_BASENAME, STAGING_BASENAME)])
    roles = ("state", "quota", "journal", "evidence")
    add("carrier_audit", None, 16777216, 1024, [path(role, SESSION_ID) for role in roles])
    for case in CASES:
        case_id = case["case_id"]; prefix = SESSION_ID + "/" + case_id
        add(case_id + "/state", case_id, 8388608, 1536, [path(role, prefix) for role in roles])
        add(case_id + "/journal", case_id, 1048576, 128, [path("journal", prefix + "/journal")])
        add(case_id + "/capture", case_id, 20971520, 384,
            [path("evidence", prefix + "/" + name) for name in ("capture", "declarations")])
        directories = ("profile-work", "profile-evidence", "profile-temporary",
                       "profile-work", "profile-evidence", "profile-temporary", "store-parent")
        for ref, directory, project in zip(ROOT_REFS, directories, case["project_ids"], strict=True):
            add(case_id + "/quota/" + ref, case_id, 1048576, 128,
                [path("quota", prefix + "/" + directory + "/" + ref)], project)
    return rows


def validate_resource_missing(value):
    require(type(value) is list, "CORE_RESOURCE_MISSING")
    order = []
    for row in value:
        exact(row, ("code", "role", "detail_sha256"), "CORE_RESOURCE_MISSING")
        require(all(type(row[key]) is str and row[key].isascii() and row[key]
                    for key in ("code", "role")), "CORE_RESOURCE_MISSING")
        digest(row["detail_sha256"], "CORE_RESOURCE_MISSING")
        order.append((row["code"], row["role"], row["detail_sha256"]))
    require(order == sorted(set(order)), "CORE_RESOURCE_MISSING")
    return value


def validate_resource_accounting(value, *, implementation, locators, guest_deadlines,
                                 admission=None, plans=(), installation=None, preparations=(), complete=True):
    """Independently verify v2's limited guarantee against bound host inputs.

    Digests bind returned evidence; they do not independently prove measurements,
    child-internal I/O, or filesystem allocation between observation boundaries.
    """
    exact(value, ("schema", "completion_adjustment", "basis", "full_guest_filesystem_peak_proven",
                  "pools", "observed_maxima_sum", "snapshot_sha256", "missing"), "CORE_RESOURCE_FIELDS")
    require(value["schema"] == RESOURCE_ACCOUNTING_SCHEMA
            and value["basis"] == "APPLICATION_AND_OBSERVED_OWNED_ALLOCATION"
            and value["full_guest_filesystem_peak_proven"] is False, "CORE_RESOURCE_GUARANTEE")
    authority = exact(value["completion_adjustment"],
        ("baseline", "owner_decision", "closure", "implementation"), "CORE_RESOURCE_AUTHORITY")
    exact(implementation, ("commit", "tree"), "CORE_RESOURCE_IMPLEMENTATION")
    for name in ("commit", "tree"):
        commit(implementation[name], "CORE_RESOURCE_IMPLEMENTATION")
        require(implementation[name] != "0" * 40, "CORE_RESOURCE_IMPLEMENTATION")
    require(authority == make_completion_adjustment(implementation), "CORE_RESOURCE_AUTHORITY")
    definitions = resource_pool_definitions(locators)
    require(type(value["pools"]) is list and len(value["pools"]) == 32, "CORE_RESOURCE_POOL_SET")
    top_missing = validate_resource_missing(value["missing"])
    require(not complete or not top_missing, "CORE_RESOURCE_INCOMPLETE")
    bound_roots = {}
    for plan in plans:
        require(type(plan) is dict and plan.get("case_id") in {case["case_id"] for case in CASES},
                "CORE_RESOURCE_PLAN")
        for row in plan["roots"]:
            identity = row["observed"]
            relative = relative_path(identity["path"], "CORE_RESOURCE_PLAN_ROOT")
            path = locators["quota_parent"] + "/" + relative
            require(any(fixed["case_id"] == plan["case_id"] and fixed["project_id"] == identity["project_id"]
                        and fixed["roots"] == [(path, "quota")] for fixed in definitions),
                    "CORE_RESOURCE_PLAN_ROOT")
            require(path not in bound_roots, "CORE_RESOURCE_PLAN")
            bound_roots[path] = {"dev": identity["device"], "ino": identity["inode"],
                                "fs_uuid": identity["filesystem_uuid"],
                                "project_id": identity["project_id"]}
    if installation is not None:
        bound_roots[installation["destination"]] = {
            "dev": installation["dev"], "ino": installation["ino"], "project_id": None}
    for prepared in preparations:
        for directory in prepared["facts"]["directories"].values():
            path = absolute_path(directory["path"])
            require(path not in bound_roots, "CORE_RESOURCE_PREPARATION_BINDING")
            bound_roots[path] = {"dev": directory["device"], "ino": directory["inode"], "project_id": None}
    parents = {} if admission is None else admission["parents"]
    absence = set() if admission is None else {
        row["name"] for row in admission["absence"]
        if row["kind"] == "path" and row["absent"] is True and row["collision"] is False}
    known_identity = {}
    owned_identity_paths = {}
    bytes_total = inodes_total = 0
    cases_total = {case["case_id"]: [0, 0] for case in CASES}
    all_observed = True
    for pool, fixed in zip(value["pools"], definitions, strict=True):
        exact(pool, ("pool_id", "case_id", "measurement_kind", "byte_limit", "inode_limit", "status",
                     "controlled_io", "last_observation", "bytes_maximum", "inodes_maximum", "missing"),
              "CORE_RESOURCE_POOL_FIELDS")
        require(all(pool[key] == fixed[key] for key in
                    ("pool_id", "case_id", "measurement_kind", "byte_limit", "inode_limit")),
                "CORE_RESOURCE_POOL_BINDING")
        require(pool["status"] in ("OBSERVED", "ABSENT", "INCOMPLETE"), "CORE_RESOURCE_POOL_STATUS")
        missing = validate_resource_missing(pool["missing"])
        require(all(row in top_missing for row in missing), "CORE_RESOURCE_MISSING_BINDING")
        io = exact(pool["controlled_io"], ("written_bytes", "created_inodes"), "CORE_RESOURCE_IO")
        for key, actual in io.items():
            if actual is None:
                require(pool["status"] == "INCOMPLETE" and any(row["role"] == pool["pool_id"] + "/controlled_io"
                        for row in missing), "CORE_RESOURCE_IO_MISSING")
            else:
                integer(actual, code="CORE_RESOURCE_IO")
        current_identities = {}
        observations = []
        for field in ("last_observation", "bytes_maximum", "inodes_maximum"):
            item = pool[field]
            if item is None:
                require(pool["status"] == "INCOMPLETE" and any(row["role"] == pool["pool_id"] + "/" + field
                        for row in missing), "CORE_RESOURCE_OBSERVATION_MISSING")
                continue
            exact(item, ("method", "boundary", "boottime_ns", "monotonic_ns", "allocated_bytes",
                         "allocated_inodes", "identities", "quota", "source_sha256"),
                  "CORE_RESOURCE_OBSERVATION_FIELDS")
            require(item["method"] in (fixed["measurement_kind"], "VERIFIED_ABSENCE")
                    and item["boundary"] in ("ADMISSION", "CONTROLLED_IO", "CHILD_BEFORE", "CHILD_AFTER",
                                              "CASE_BOUNDARY", "FINALIZATION"), "CORE_RESOURCE_METHOD")
            require(type(guest_deadlines) is dict, "CORE_RESOURCE_WINDOW")
            for clock in ("boottime", "monotonic"):
                integer(item[clock + "_ns"], code="CORE_RESOURCE_WINDOW")
                require(guest_deadlines[clock + "_origin_ns"] <= item[clock + "_ns"]
                        < guest_deadlines[clock + "_deadline_ns"], "CORE_RESOURCE_WINDOW")
            for key, limit in (("allocated_bytes", fixed["byte_limit"]),
                               ("allocated_inodes", fixed["inode_limit"])):
                integer(item[key], code="CORE_RESOURCE_ALLOCATION")
                require(not complete or item[key] <= limit, "CORE_RESOURCE_POOL_LIMIT")
            preimage = {"pool_id": pool["pool_id"], "case_id": pool["case_id"],
                        "observation": {key: actual for key, actual in item.items() if key != "source_sha256"}}
            require(item["source_sha256"] == sha256(canonical(preimage)), "CORE_RESOURCE_SOURCE_DIGEST")
            identities = item["identities"]
            require(type(identities) is list and 1 <= len(identities) <= 16 and admission is not None,
                    "CORE_RESOURCE_IDENTITIES")
            paths = []; covered = set()
            present_paths = {pin.get("path") for pin in identities
                             if type(pin) is dict and pin.get("role") == "POOL_ROOT"}
            for identity in identities:
                exact(identity, ("path", "role", "dev", "ino", "fs_uuid", "project_id"),
                      "CORE_RESOURCE_IDENTITY_FIELDS")
                path = absolute_path(identity["path"], "CORE_RESOURCE_IDENTITY_PATH"); paths.append(path)
                integer(identity["dev"], code="CORE_RESOURCE_IDENTITY")
                integer(identity["ino"], 1, code="CORE_RESOURCE_IDENTITY")
                require(type(identity["fs_uuid"]) is str and re.fullmatch(
                    r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", identity["fs_uuid"]),
                    "CORE_RESOURCE_IDENTITY")
                require(identity["role"] in ("POOL_ROOT", "ABSENCE_PARENT"), "CORE_RESOURCE_IDENTITY")
                matches = []
                for root, role in fixed["roots"]:
                    parent = parents[role]
                    if identity["role"] == "POOL_ROOT" and path == root:
                        matches.append(root)
                    elif identity["role"] == "ABSENCE_PARENT" and root in absence and root not in present_paths:
                        if path == parent["path"] or root.startswith(path + "/") and (
                                path in known_identity or path in bound_roots):
                            matches.append(root)
                    if root in matches:
                        require(identity["dev"] == parent["dev"] and identity["fs_uuid"] == parent["fs_uuid"],
                                "CORE_RESOURCE_DEVICE_BINDING")
                require(matches and not covered.intersection(matches), "CORE_RESOURCE_ROOT_COVERAGE")
                covered.update(matches)
                if identity["role"] == "ABSENCE_PARENT":
                    expected = next((parent for parent in parents.values() if parent.get("path") == path),
                                    known_identity.get(path, bound_roots.get(path)))
                    require(expected is not None and all(identity[key] == expected[key] for key in
                            ("dev", "ino")) and ("fs_uuid" not in expected or identity["fs_uuid"] == expected["fs_uuid"])
                            and identity["project_id"] is None,
                            "CORE_RESOURCE_ABSENCE_BINDING")
                else:
                    require(identity["project_id"] == fixed["project_id"], "CORE_RESOURCE_PROJECT_BINDING")
                    expected = bound_roots.get(path)
                    require(fixed["project_id"] is None or expected is not None, "CORE_RESOURCE_PREPARATION_BINDING")
                    require(expected is None or all(identity[key] == actual for key, actual in expected.items()),
                            "CORE_RESOURCE_PREPARATION_BINDING")
                    inode_key = (identity["dev"], identity["ino"])
                    require(inode_key not in owned_identity_paths or owned_identity_paths[inode_key] == path,
                            "CORE_RESOURCE_ROOT_ALIAS")
                    owned_identity_paths[inode_key] = path
                key = (path, identity["role"])
                require(key not in current_identities or current_identities[key] == identity,
                        "CORE_RESOURCE_IDENTITY_DRIFT")
                current_identities[key] = identity
            require(paths == sorted(set(paths)) and covered == {root for root, _ in fixed["roots"]},
                    "CORE_RESOURCE_ROOT_COVERAGE")
            if item["method"] == "VERIFIED_ABSENCE":
                require(item["allocated_bytes"] == item["allocated_inodes"] == 0
                        and item["quota"] is None
                        and all(identity["role"] == "ABSENCE_PARENT" for identity in identities),
                        "CORE_RESOURCE_ABSENCE")
            elif item["method"] == "PROJECT_QUOTA":
                quota = exact(item["quota"], ("project_id", "hard_bytes", "hard_inodes", "used_bytes",
                                              "used_inodes", "enforcement_flags"), "CORE_RESOURCE_QUOTA")
                require(len(identities) == 1 and identities[0]["role"] == "POOL_ROOT"
                        and quota["project_id"] == fixed["project_id"]
                        and quota["hard_bytes"] == fixed["byte_limit"]
                        and quota["hard_inodes"] == fixed["inode_limit"]
                        and quota["used_bytes"] == item["allocated_bytes"]
                        and quota["used_inodes"] == item["allocated_inodes"], "CORE_RESOURCE_QUOTA")
                for key in quota:
                    integer(quota[key], code="CORE_RESOURCE_QUOTA")
                require(quota["enforcement_flags"] & 0x30 == 0x30, "CORE_RESOURCE_QUOTA_ENFORCEMENT")
            else:
                require(item["quota"] is None, "CORE_RESOURCE_QUOTA")
            observations.append(item)
        if pool["status"] == "INCOMPLETE":
            require(missing and not complete, "CORE_RESOURCE_INCOMPLETE")
            all_observed = False
        else:
            require(not missing and len(observations) == 3 and all(actual is not None for actual in io.values()),
                    "CORE_RESOURCE_INCOMPLETE")
            method = "VERIFIED_ABSENCE" if pool["status"] == "ABSENT" else fixed["measurement_kind"]
            require(all(item["method"] == method for item in observations), "CORE_RESOURCE_STATUS_METHOD")
            require(not complete or pool["last_observation"]["boundary"] == "FINALIZATION",
                    "CORE_RESOURCE_FINAL_BOUNDARY")
            if pool["status"] == "ABSENT":
                require(io == {"written_bytes": 0, "created_inodes": 0}
                        and not any(path == root or path.startswith(root + "/")
                                    for root, _ in fixed["roots"] for path in bound_roots),
                        "CORE_RESOURCE_ABSENCE_IO")
        last = pool["last_observation"]
        if last is not None:
            for field in ("bytes_maximum", "inodes_maximum"):
                maximum = pool[field]
                if maximum is not None:
                    require(all(maximum[clock + "_ns"] <= last[clock + "_ns"]
                                for clock in ("boottime", "monotonic")), "CORE_RESOURCE_TIME_ORDER")
        for field, amount in (("bytes_maximum", "allocated_bytes"), ("inodes_maximum", "allocated_inodes")):
            maximum = pool[field]
            if maximum is not None:
                require(all(maximum[amount] >= item[amount] for item in observations), "CORE_RESOURCE_MAXIMUM")
        for (_, role), identity in current_identities.items():
            if role == "POOL_ROOT":
                previous = known_identity.get(identity["path"])
                require(previous is None or previous == identity, "CORE_RESOURCE_IDENTITY_DRIFT")
                known_identity[identity["path"]] = identity
        if pool["status"] != "INCOMPLETE":
            amounts = (pool["bytes_maximum"]["allocated_bytes"], pool["inodes_maximum"]["allocated_inodes"])
            bytes_total += amounts[0]; inodes_total += amounts[1]
            if fixed["case_id"] is not None:
                subtotal = cases_total[fixed["case_id"]]
                subtotal[0] += amounts[0]; subtotal[1] += amounts[1]
    totals = exact(value["observed_maxima_sum"], ("bytes", "inodes"), "CORE_RESOURCE_TOTAL_FIELDS")
    require(totals == ({"bytes": bytes_total, "inodes": inodes_total} if all_observed
                       else {"bytes": None, "inodes": None}), "CORE_RESOURCE_TOTAL_BINDING")
    require(not complete or bytes_total <= LIMITS["total_guest_physical_bytes"]
            and inodes_total <= LIMITS["total_guest_physical_inodes"]
            and all(amount[0] <= LIMITS["case_physical_bytes"] and amount[1] <= LIMITS["case_physical_inodes"]
                    for amount in cases_total.values()), "CORE_RESOURCE_TOTAL_LIMIT")
    snapshot = {key: value[key] for key in ("completion_adjustment", "pools", "observed_maxima_sum")}
    require(value["snapshot_sha256"] == sha256(canonical(snapshot)), "CORE_RESOURCE_SNAPSHOT_DIGEST")
    return value


APPROVED_COMPONENTS = (
    "source_relation", "policy_basis", "historical_capacity_obligations",
    "retained_preparation", "reconciliation",
)
ADMISSION_BINDING_FIELDS = (
    "approved_inputs_sha256", "approved_source_relation_sha256", "policy_basis_sha256",
    "historical_capacity_obligations_sha256", "retained_preparation_sha256", "reconciliation_sha256",
    "local_management_binding_sha256", "hello_sha256", "remote_management_sha256",
)


def validate_approved_inputs(value, *, amendment=None):
    """Validate only the wire envelope, not private source or live admission."""
    exact(value, {"schema", "scope", "amendment", *APPROVED_COMPONENTS}, "CORE_APPROVED_INPUTS_FIELDS")
    require(value["schema"] == APPROVED_INPUTS_SCHEMA and value["scope"] == SCOPE,
            "CORE_APPROVED_INPUTS_SCHEMA")
    validate_amendment(value["amendment"])
    require(amendment is None or value["amendment"] == amendment, "CORE_APPROVED_INPUTS_AMENDMENT")
    require(all(type(value[key]) is dict and value[key] for key in APPROVED_COMPONENTS),
            "CORE_APPROVED_INPUTS_COMPONENT")
    canonical(value, newline=True, limit=APPROVED_INPUTS_LIMIT)
    return value


def admission_binding(approved_inputs_raw, local_management_binding, hello, *, amendment=None):
    """Compute nine distinct preimages, without claiming source/live admission."""
    approved = validate_approved_inputs(document(approved_inputs_raw,
        limit=APPROVED_INPUTS_LIMIT, newline=True), amendment=amendment)
    validate_record(local_management_binding, MANAGEMENT_BINDING_SCHEMA)
    validate_hello(hello, remote_expectation=local_management_binding["remote_expectation"])
    result = {"approved_inputs_sha256": sha256(approved_inputs_raw)}
    for component, field in zip(APPROVED_COMPONENTS, ADMISSION_BINDING_FIELDS[1:6], strict=True):
        result[field] = sha256(canonical(approved[component]))
    result.update(local_management_binding_sha256=sha256(canonical(local_management_binding, newline=True)),
        hello_sha256=sha256(canonical(hello, newline=True)),
        remote_management_sha256=sha256(canonical(hello["remote_management"])))
    return result


def validate_admission_binding(value, *, approved_inputs_raw, local_management_binding, hello,
                               amendment=None):
    exact(value, ADMISSION_BINDING_FIELDS, "CORE_ADMISSION_BINDING_FIELDS")
    require(value == admission_binding(approved_inputs_raw, local_management_binding, hello,
                                       amendment=amendment), "CORE_ADMISSION_BINDING")
    return value


def validate_bind(value):
    validate_record(value, "local-hand-q2-core-carrier-bind/v1")
    require(value["scope"] == SCOPE and value["session_id"] == SESSION_ID, "CORE_BIND_AUTHORITY")
    for key in ("hello_sha256", "consumption_sha256", "package_sha256"):
        digest(value[key], "CORE_BIND_DIGEST")
    validate_package_basename(value["package_basename"])
    require(value["package_basename"] == SESSION_ID + '.lhfp', 'CORE_BIND_PACKAGE')
    integer(value["package_bytes"], 1, PACKAGE_LIMITS["package_bytes"], "CORE_BIND_PACKAGE")
    for key in SCHEMA_FIELDS[value["schema"]][8:]:
        integer(value[key], 1 if key in ("mapped_duration_ns", "guest_duration_ns") else 0,
                code="CORE_BIND_CLOCK")
    require(value["host_boottime_deadline_ns"]
            == value["host_boottime_origin_ns"] + 1800000000000
            and value["host_monotonic_deadline_ns"]
            == value["host_monotonic_origin_ns"] + 1800000000000
            and value["host_boottime_bind_ns"] >= value["host_boottime_origin_ns"]
            and value["host_monotonic_bind_ns"] >= value["host_monotonic_origin_ns"],
            "CORE_BIND_HOST_WINDOW")
    require(value["clock_margin_ns"] == 2_000_000_000
            and value["local_final_reserve_ns"] == 30000000000
            and value["guest_duration_cap_ns"] == 1500000000000, "CORE_BIND_LIMIT")
    remaining = min(value["host_boottime_deadline_ns"] - value["host_boottime_bind_ns"],
                    value["host_monotonic_deadline_ns"] - value["host_monotonic_bind_ns"])
    expected_floor = remaining // 1_000_000 * 1_000_000
    require(value["host_boottime_deadline_ns"]
                == value["host_boottime_origin_ns"] + 1800000000000
            and value["host_monotonic_deadline_ns"]
                == value["host_monotonic_origin_ns"] + 1800000000000
            and value["host_boottime_origin_ns"] <= value["host_boottime_bind_ns"]
            and value["host_monotonic_origin_ns"] <= value["host_monotonic_bind_ns"]
            and remaining > 0 and value["host_remaining_floor_ns"] == expected_floor
            and value["mapped_duration_ns"] == expected_floor - value["clock_margin_ns"]
                - value["local_final_reserve_ns"] > 0
            and value["guest_duration_ns"] == min(value["mapped_duration_ns"],
                                                  value["guest_duration_cap_ns"]),
            "CORE_BIND_MAPPING")
    return value


def validate_remote_management(value, *, expectation=None):
    fields = {"account", "uid", "gid", "home", "login_shell", "parser_profile", "shell",
              "sudo", "env", "systemd_run", "python", "remote_tokens_sha256", "remote_command_sha256"}
    exact(value, fields, "CORE_HELLO_REMOTE_FIELDS")
    require(value["account"] == "q1admin" and value["home"] == "/home/q1admin"
            and value["login_shell"] == "/bin/bash"
            and value["parser_profile"] == "bash-noninteractive-c-v1", "CORE_HELLO_REMOTE_ACCOUNT")
    integer(value["uid"], 1, code="CORE_HELLO_REMOTE_ACCOUNT")
    integer(value["gid"], 1, code="CORE_HELLO_REMOTE_ACCOUNT")
    aliases = {"shell": value["login_shell"], "sudo": "/usr/bin/sudo", "env": "/usr/bin/env",
               "systemd_run": "/usr/bin/systemd-run", "python": "/usr/bin/python3"}
    entity_fields = {"path", "resolved_path", "symlink_chain", "dev", "ino", "mode", "uid", "gid",
                     "nlink", "bytes", "sha256"}
    for role, alias in aliases.items():
        entity = exact(value[role], entity_fields, "CORE_HELLO_REMOTE_ENTITY_FIELDS")
        require(entity["path"] == alias, "CORE_HELLO_REMOTE_ALIAS")
        absolute_path(entity["resolved_path"], "CORE_HELLO_REMOTE_PATH")
        require(len(PurePosixPath(entity["resolved_path"]).parts) - 1 <= 64, "CORE_HELLO_REMOTE_PATH")
        integer(entity["dev"], code="CORE_HELLO_REMOTE_ENTITY")
        integer(entity["ino"], 1, code="CORE_HELLO_REMOTE_ENTITY")
        integer(entity["mode"], 0, 0o7777, "CORE_HELLO_REMOTE_ENTITY")
        integer(entity["uid"], 0, 0, "CORE_HELLO_REMOTE_ENTITY")
        integer(entity["gid"], 0, 0, "CORE_HELLO_REMOTE_ENTITY")
        integer(entity["nlink"], 1, 1, "CORE_HELLO_REMOTE_ENTITY")
        integer(entity["bytes"], 1, 16777216, "CORE_HELLO_REMOTE_ENTITY")
        require(entity["mode"] & 0o111 and not entity["mode"] & 0o022, "CORE_HELLO_REMOTE_ENTITY")
        digest(entity["sha256"], "CORE_HELLO_REMOTE_ENTITY")
        chain = entity["symlink_chain"]
        require(type(chain) is list and len(chain) <= 8, "CORE_HELLO_REMOTE_SYMLINK")
        seen = set()
        for link in chain:
            exact(link, {"path", "target"}, "CORE_HELLO_REMOTE_SYMLINK")
            absolute_path(link["path"], "CORE_HELLO_REMOTE_SYMLINK")
            target = link["target"]
            require(type(target) is str and target and "\0" not in target
                    and len(target.encode("utf-8")) <= 4096 and ".." not in PurePosixPath(target).parts
                    and len(PurePosixPath(target).parts) <= 65
                    and link["path"] not in seen, "CORE_HELLO_REMOTE_SYMLINK")
            seen.add(link["path"])
    for field in ("remote_tokens_sha256", "remote_command_sha256"):
        digest(value[field], "CORE_HELLO_REMOTE_COMMAND")
    if expectation is not None:
        exact(expectation, {"account", "home_path", "login_shell", "hello_schema", "parser_profile",
              "aliases", "remote_tokens_sha256", "remote_command_sha256", "remote_entity_preimages_stage"},
              "CORE_HELLO_EXPECTATION_FIELDS")
        require(expectation["account"] == value["account"]
                and expectation["home_path"] == value["home"]
                and expectation["login_shell"] == value["login_shell"]
                and expectation["hello_schema"] == HELLO_SCHEMA
                and expectation["parser_profile"] == value["parser_profile"]
                and expectation["aliases"] == aliases
                and expectation["remote_entity_preimages_stage"] == "HELLO_JIT"
                and all(expectation[k] == value[k] for k in
                        ("remote_tokens_sha256", "remote_command_sha256")), "CORE_HELLO_REMOTE_EXPECTATION")
    return value


def validate_hello(value, *, loader_sha256=None, bootstrap_sha256=None, remote_expectation=None):
    return _validate_hello_identity(value, carrier_unit=CARRIER_UNIT,
        loader_sha256=loader_sha256, bootstrap_sha256=bootstrap_sha256,
        remote_expectation=remote_expectation)


def _validate_hello_identity(value, *, carrier_unit, loader_sha256=None,
                             bootstrap_sha256=None, remote_expectation=None):
    """Frozen HELLO grammar; historical callers bind their original unit and sources."""
    factor = 2 if carrier_unit == CARRIER_UNIT else 1
    validate_record(value, HELLO_SCHEMA)
    require(value["scope"] == SCOPE, "CORE_HELLO_AUTHORITY")
    for key, expected in (("loader_sha256", loader_sha256),
                          ("bootstrap_sha256", bootstrap_sha256)):
        digest(value[key], "CORE_HELLO_DIGEST")
        require(expected is None or value[key] == expected, "CORE_HELLO_DIGEST")
    require(type(value["guest_boot_id"]) is str
            and re.fullmatch(r"[0-9a-f-]{36}", value["guest_boot_id"])
            and all(type(value[key]) is int and value[key] > 0 for key in
                    ("guest_boottime_origin_ns", "guest_monotonic_origin_ns", "pid"))
            and all(type(value[key]) is int and value[key] == 0 for key in ("uid", "gid", "euid", "egid")),
            "CORE_HELLO_IDENTITY")
    python = exact(value["python"],
        {"path", "dev", "ino", "mode", "uid", "gid", "nlink", "bytes", "sha256"},
        "CORE_HELLO_PYTHON")
    absolute_path(python["path"], "CORE_HELLO_PYTHON")
    digest(python["sha256"], "CORE_HELLO_PYTHON")
    require(all(type(python[key]) is int for key in
                ("dev", "ino", "mode", "uid", "gid", "nlink", "bytes"))
            and python["dev"] >= 0 and python["ino"] > 0 and python["mode"] & 0o111
            and python["uid"] == python["gid"] == 0 and python["nlink"] == 1
            and python["bytes"] > 0, "CORE_HELLO_PYTHON")
    remote = validate_remote_management(value["remote_management"], expectation=remote_expectation)
    projected = {key: remote["python"][key] for key in python if key != "path"}
    projected["path"] = remote["python"]["resolved_path"]
    require(python == projected, "CORE_HELLO_PYTHON_BINDING")
    unit = exact(value["carrier_unit"],
        {"name", "control_group", "invocation_id", "active_state", "sub_state",
         "runtime_max_usec", "timeout_stop_usec", "memory_max", "memory_swap_max",
         "tasks_max", "cpu_quota_per_sec_usec", "restart", "kill_mode", "exit_type"},
        "CORE_HELLO_CARRIER")
    require(unit["name"] == carrier_unit and unit["control_group"].endswith("/" + carrier_unit)
            and re.fullmatch(r"[0-9a-f]{32}", unit["invocation_id"] or "")
            and unit["active_state"] == "active" and unit["sub_state"] in ("running", "start")
            and unit["runtime_max_usec"] == (800000000 * factor)
            and unit["timeout_stop_usec"] == (30000000 * factor)
            and unit["memory_max"] == (1073741824 * factor) and unit["memory_swap_max"] == 0
            and unit["tasks_max"] == (128 * factor) and unit["cpu_quota_per_sec_usec"] == (1000000 * factor)
            and unit["restart"] == "no" and unit["kill_mode"] == "control-group"
            and unit["exit_type"] == "cgroup", "CORE_HELLO_CARRIER")
    process = exact(value["process_limits"],
        {"cpu_soft", "cpu_hard", "nofile_soft", "nofile_hard", "fsize_soft", "fsize_hard", "umask"},
        "CORE_HELLO_PROCESS_LIMITS")
    require(process == {"cpu_soft": (800 * factor), "cpu_hard": (800 * factor), "nofile_soft": (256 * factor),
                        "nofile_hard": (256 * factor), "fsize_soft": (67108864 * factor),
                        "fsize_hard": (67108864 * factor), "umask": 0o077},
            "CORE_HELLO_PROCESS_LIMITS")
    require(len(canonical(value, newline=True)) <= (4096 * factor), "CORE_HELLO_LIMIT")
    return value


def validate_state_path(states):
    require(type(states) is list and states, "CORE_STATE_PATH")
    require(states[0] in (LOCAL_STATES[0], REMOTE_STATES[0]), "CORE_STATE_PATH")
    local = states[0] == LOCAL_STATES[0]
    chain = list(LOCAL_STATES if local else REMOTE_STATES)
    terminal = "STOP_AND_RETAIN" if local else "REMOTE_STOP_AND_RETAIN"
    require(all(type(item) is str for item in states), "CORE_STATE_PATH")
    if states[-1] == terminal:
        body = states[:-1]
    else:
        body = states
    require(body == chain[:len(body)] and (states[-1] == terminal or len(body) == len(states)),
            "CORE_STATE_PATH")
    return states

# Exact Owner-approved VM adoption closure; field admission remains independent.
VM_ADOPTION_SCOPE = "LH-Q2-CORE-VM-ADOPTION-CONTINUATION-v1"
VM_ADOPTION_BASELINE = {'commit': '13cd2d3e7ac9a307a7c960f713524fefa2959a95', 'tree': '9e7ab5eb4b555cfcd33ce1d7aa56f11e26b1055d', 'documents_sha256': {'docs/a2-execution/q2-core-vm-adoption-continuation/ARCHITECTURE.md': '5ca95b118dcf267efe2db2f822341d621c9b22d3cac3f6fbfe7b3c2b2c20eba4', 'docs/a2-execution/q2-core-vm-adoption-continuation/IMPLEMENTATION_PLAN.md': 'de5273f46a01c9412e75abab2a5a222662137d10a8c487f9069d7c9e5819282d', 'docs/a2-execution/q2-core-vm-adoption-continuation/REQUIREMENTS.md': '15a4955d572f16baf9775bb752b2640db2dddcae8d6ad3b7577ab7c64a27c496'}}
VM_ADOPTION_OWNER_DECISION = {'event': 'LH-Q2-CORE-VM-ADOPTION-CONTINUATION-CLOSURE-20261009-01', 'record_path': 'docs/governance/Q2_CORE_VM_ADOPTION_CONTINUATION_OWNER_DECISION.md', 'record_sha256': '740cb305e75041687f4c229fbecd7d58469993b93b76566000e6a7181758488c'}
VM_ADOPTION_CLOSURE = {'commit': '31b8e21116edd3678d738c1b9525edb6b3da8ae8', 'tree': 'ff085251c03910410abe54666999ff47b28d4a92'}

# Exact runtime continuation; this closes scope, not field readiness.
RUNTIME_SCOPE = "LH-Q2-CORE-RUNTIME-CONTINUATION-v1"
RUNTIME_BASELINE = dict(commit="dc6e6c511936e02f41cda0cf86cbd571f3aa253d",
    tree="01fa3c68860a2e5106e9d3e59fdb1b9efe63d7b1", documents_sha256={
    "docs/a2-execution/q2-core-runtime-continuation/REQUIREMENTS.md": "35311cf40446b9e87047e74fcb4cbc04c31e6b088c0db382a34d8c789e952448",
    "docs/a2-execution/q2-core-runtime-continuation/ARCHITECTURE.md": "97e44b405a8c7b89e116e7578c81f6ce97f2f85e2950c6aaa9cdef1e0b386b63",
    "docs/a2-execution/q2-core-runtime-continuation/IMPLEMENTATION_PLAN.md": "bfb3d448210c01cff0fdae3088eb5f90ea19d978df842b6c773234c5bff40b78"})
RUNTIME_OWNER_DECISION = dict(event="LH-Q2-CORE-RUNTIME-CONTINUATION-CLOSURE-20261009-01",
    record_path="docs/governance/Q2_CORE_RUNTIME_CONTINUATION_OWNER_DECISION.md",
    record_sha256="dbee48fb03ec19bc98486422ad813d50139a68261bb6e1c905daf4823ac72cd1")
RUNTIME_CLOSURE = dict(commit="3633b1e963b35647bef8d7f94592089130ff25a1",
    tree="d51352ba8d9964745ca7fdda2f05a0a8469da8a7")

# Exact host FD continuation; scope approval does not establish field success.
HOST_FD_SCOPE = "LH-Q2-CORE-HOST-FD-CONTINUATION-v1"
HOST_FD_BASELINE = {'commit': '0ed9ba0a8eefa4d1a88ee46192fc18a5ad3fafc8', 'tree': 'c29e7439e85229d926a7c632ef1da1a40e95ef7e', 'documents_sha256': {'docs/a2-execution/q2-core-host-fd-continuation/ARCHITECTURE.md': '48ade8d19b733ed167f056e83b232ad2c41030add31354d9323f613128c30557', 'docs/a2-execution/q2-core-host-fd-continuation/IMPLEMENTATION_PLAN.md': '1cd7d46c870ee630edd883a9cc00104a90a6f2edfde62304327e36a5155d391c', 'docs/a2-execution/q2-core-host-fd-continuation/REQUIREMENTS.md': '06cdab5674d06eb614425585e7c45327fe65975f808800eb8432170626fdd718'}}
HOST_FD_OWNER_DECISION = {'event': 'LH-Q2-CORE-HOST-FD-CONTINUATION-CLOSURE-20261009-01', 'record_path': 'docs/governance/Q2_CORE_HOST_FD_CONTINUATION_OWNER_DECISION.md', 'record_sha256': '83ae33bd9f5ae7234a87cb74afe5644545f5756c8ae8eeb22b9a0ab398bce42d'}
HOST_FD_CLOSURE = {'commit': '26a89a1a11a958c24987eb590944331a9769b2ad', 'tree': '8a53bcc57200157d246ccc3140866046a8079250'}

USAGE_SCOPE = "LH-Q2-CORE-USAGE-CONTINUATION-v1"
USAGE_BASELINE = {'commit': 'bb75dfd835640ba3fff5d1124b7820b0aecf87e5', 'tree': '066b1c014c1ce7947f223704a0dbf06969c252a3', 'documents_sha256': {'docs/a2-execution/q2-core-usage-continuation/ARCHITECTURE.md': 'eba4000ed3a4632f19cc3fcff5472f207b2b067fa70237ebee20012d463b02a8', 'docs/a2-execution/q2-core-usage-continuation/IMPLEMENTATION_PLAN.md': '2591dc8749d71c2f013c158817e27cde23d025e085d4fcddb3f5dfecd73b8a72', 'docs/a2-execution/q2-core-usage-continuation/REQUIREMENTS.md': 'e3df5820643ed238fadd8b727351bc04f3e171e7be4c16237849eb63d1f7ece0'}}
USAGE_OWNER_DECISION = {'event': 'LH-Q2-CORE-USAGE-CONTINUATION-CLOSURE-20261010-01', 'record_path': 'docs/governance/Q2_CORE_USAGE_CONTINUATION_OWNER_DECISION.md', 'record_sha256': '222811e17d9d96d88fd0c9862f0ff8fa80dc628d3a9037aeb4abe82bf09c3c7c'}
USAGE_CLOSURE = {'commit': '2a4282800eaae404ff3163446cc06297ce99526a', 'tree': 'f28e01643fe8d1015efdda07caf762dc53450b96'}

TRANSPORT_SCOPE = "LH-Q2-CORE-TRANSPORT-CONTINUATION-v1"
TRANSPORT_BASELINE = {'commit': 'b55315822472bfb0c9672426392ef1579466f44d', 'tree': '99680c393c82e038730e29da72b8b3311e0ff6c8', 'documents_sha256': {'docs/a2-execution/q2-core-transport-continuation/ARCHITECTURE.md': 'a65ae4d2db4dec946ebf90c1ef454322b0f27abcea0bd73932d4555e8a220616', 'docs/a2-execution/q2-core-transport-continuation/IMPLEMENTATION_PLAN.md': '9960f24145e7e22a4fd8e9d254971193c030ce9d2a9260094f4454eb7a8c1b35', 'docs/a2-execution/q2-core-transport-continuation/REQUIREMENTS.md': '06925433b0d9ca47c83e5fb8973637a2467e2de0bbf8dcff0a1a3962b8f77e57'}}
TRANSPORT_OWNER_DECISION = {'event': 'LH-Q2-CORE-TRANSPORT-CONTINUATION-CLOSURE-20261010-01', 'record_path': 'docs/governance/Q2_CORE_TRANSPORT_CONTINUATION_OWNER_DECISION.md', 'record_sha256': '26540ac4981db4324e253ac174646bf47b62b0a735615d7648a92e2cab9570c1'}
TRANSPORT_CLOSURE = {'commit': '2bac65db690759bfe89a03228dc3b5186056569d', 'tree': 'bb3cd32637c9e41652b96661be3449a8e0cb5b52'}

RESUMED_VM_SCOPE = "LH-Q2-CORE-RESUMED-VM-v1"
RESUMED_VM_BASELINE = {'commit': 'b0aa74f9f7a75d70a82575a2e679e540bb47dc1f', 'tree': 'ab4861032919d3db94c937100d713e3a35b81ba1', 'documents_sha256': {'docs/a2-execution/q2-core-resumed-vm/ARCHITECTURE.md': 'b194587e2860f38a77b789bbc55053cd167c8b21bccd0160aaf5f59011da7fd8', 'docs/a2-execution/q2-core-resumed-vm/IMPLEMENTATION_PLAN.md': 'a3d0017794c63e50e4ce3472df4260993bfc298e19c8f4bf0611794c0e0b69fb', 'docs/a2-execution/q2-core-resumed-vm/REQUIREMENTS.md': '7812cf87ef8e8d140d33cb05d37aabfe1705f045ed7fd2b73c98e532c25d0ca5'}}
RESUMED_VM_OWNER_DECISION = {'event': 'LH-Q2-CORE-RESUMED-VM-CLOSURE-20261010-01', 'record_path': 'docs/governance/Q2_CORE_RESUMED_VM_OWNER_DECISION.md', 'record_sha256': '00136ef85db3dacd57c0babe8e10960576c9c5abf428e5405534192257ffac5b'}
RESUMED_VM_CLOSURE = {'commit': 'a4e2203402e2b8958d8a2339cc3bc5f7e422572c', 'tree': '5520e64a3d0496f31353a8d617e1f94e53b1b47c'}

# Exact protected-source continuation; the old guest failure remains retained.
PROTECTED_SOURCE_SCOPE = "LH-Q2-CORE-PROTECTED-SOURCE-v1"
PROTECTED_SOURCE_BASELINE = {'commit': 'eabffdbfbdc1c2d041f35dd9371714625380bf3f', 'tree': '0de0a04ed246bbbc95b20f30696214a1ed6354d9', 'documents_sha256': {'docs/a2-execution/q2-core-protected-source/ARCHITECTURE.md': '94a271782fa4edcba92640cf0998da6797ae7044292d75d45b26c0e698b427ef', 'docs/a2-execution/q2-core-protected-source/IMPLEMENTATION_PLAN.md': '8a473e30346b3037b520f3d2c0450591aac66e1c1bc43bbe80f80d0d3581139c', 'docs/a2-execution/q2-core-protected-source/REQUIREMENTS.md': '3c9bfaf6f0692dccd8b2c259dd3916d523e5e0718451543e37f0761dac449aef'}}
PROTECTED_SOURCE_OWNER_DECISION = {'event': 'LH-Q2-CORE-PROTECTED-SOURCE-CLOSURE-20261010-01', 'record_path': 'docs/governance/Q2_CORE_PROTECTED_SOURCE_OWNER_DECISION.md', 'record_sha256': 'c238fd58b5259b2585782f44a9570b5ccc0ce22ac87b640d51f27b0a9f5da418'}
PROTECTED_SOURCE_CLOSURE = {'commit': 'a6532946abf9e4f1364622398112e681c35de2ec', 'tree': '6985dc0ba960bd63af23cbfe77995a02ea9820fb'}


PERSISTENT_PATH_SCOPE = "LH-Q2-CORE-PERSISTENT-PATH-CONTINUATION-v1"
PERSISTENT_PATH_BASELINE = {'commit': '4b8e24c1985b19aea957044e5936f4146301c247', 'tree': '0d4786fecdb1ef1d41e3ad590f4b1a3d7993b017', 'documents_sha256': {'docs/a2-execution/q2-core-persistent-path-continuation/ARCHITECTURE.md': 'cae3da72c9552774ce2612529b5f887a4d0cbd475ea9e54bad18a0f948f51e3c', 'docs/a2-execution/q2-core-persistent-path-continuation/IMPLEMENTATION_PLAN.md': 'cf9aa3b6b84d22c4b81d78b3d5a8951b895333f851af819ecb0844dc32f4a663', 'docs/a2-execution/q2-core-persistent-path-continuation/REQUIREMENTS.md': '62bc1a896b907380631644bead64a7a6e0bf3c7c318f3f3267b6396836b6bfbc'}}
PERSISTENT_PATH_OWNER_DECISION = {'event': 'LH-Q2-CORE-PERSISTENT-PATH-CONTINUATION-CLOSURE-20261010-01', 'record_path': 'docs/governance/Q2_CORE_PERSISTENT_PATH_CONTINUATION_OWNER_DECISION.md', 'record_sha256': '4b21f61cb3106d7e558bb53d1a13bbca907f95012c1bfc8cf33198a3dcff81b0'}
PERSISTENT_PATH_CLOSURE = {'commit': 'd77315e5792c54c406b000b2179ef179ec900c94', 'tree': '9b0e73eac83bb2c6bed3722b0b8c8e7b122d6c49'}

IDENTITY_RESOURCE_SCOPE = "LH-Q2-CORE-IDENTITY-RESOURCE-CONTINUATION-v1"
IDENTITY_RESOURCE_BASELINE = {'commit': 'e16b9038eb825f06306a6fe94bc2be30cc418238', 'tree': '40a9ed9c36bee97409acaac319678613d970a037', 'documents_sha256': {'docs/a2-execution/q2-core-identity-resource-continuation/ARCHITECTURE.md': '6553f8417ce1f9fc2f680cd54ccb6e3b29f3866a9e845e29a1b03f81d8f270f6', 'docs/a2-execution/q2-core-identity-resource-continuation/IMPLEMENTATION_PLAN.md': '1e68d4516f400b1e8cf571a4705e0a8e833641df53c7841626f985af6061e57d', 'docs/a2-execution/q2-core-identity-resource-continuation/REQUIREMENTS.md': 'f682209fb3c7cd66a81c30386d97869a255dd02f073847eebadb2dd8d46fcde9'}}
IDENTITY_RESOURCE_OWNER_DECISION = {'event': 'LH-Q2-CORE-IDENTITY-RESOURCE-CONTINUATION-CLOSURE-20261011-01', 'record_path': 'docs/governance/Q2_CORE_IDENTITY_RESOURCE_CONTINUATION_OWNER_DECISION.md', 'record_sha256': 'fa41d6f6938cc59ad65487ca9d813a832807dbd829aa53f46299504688eb179c'}
IDENTITY_RESOURCE_CLOSURE = {'commit': 'f74725156ed0fa5bfc1c9760ca9efd1afd110870', 'tree': '0d489734dfe05d1f9348d0539ea8f56f5384e817'}
