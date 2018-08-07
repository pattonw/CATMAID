# -*- coding: utf-8 -*-

import os
import subprocess

from datetime import datetime

from django.conf import settings
from django.http import JsonResponse, HttpResponse

from catmaid.control.common import get_request_bool, urljoin
from catmaid.control.authentication import requires_user_role
from catmaid.models import Message, User, UserRole

from celery.task import task

from rest_framework.authtoken.models import Token


# The path were server side exported files get stored in
output_path = os.path.join(settings.MEDIA_ROOT, settings.MEDIA_EXPORT_SUBDIRECTORY)


# @requires_user_role(UserRole.Annotate)
def flood_fill_skeleton(request):
    """
    Flood fill a skeleton. Necessary information:
    Server configuration
    volume toml
    model toml
    """
    for i in range(10):
        print("")
    for uploadedfile in request.FILES.values():
        for i in range(10):
            print("size: ")
            print(uploadedfile.size)
    for i in range(10):
        print("")
    return JsonResponse({x: request.POST[x] for x in request.POST})


@task()
def flood_fill_async():
    """
    Connect to the server and run the script
    """
    return None


def flood_fill():
    bash_script = """#!/usr/bin/env bash
ssh {server_address}
source {environment_path}
cd {work_folder}
{flood_fill_command}
scp {output_files} {media_folder}""".format(
        **{
            "server_address": "server",
            "environment_path": "environment",
            "work_folder": "work_path",
            "flood_fill_command": "python -m diluvian fill",
            "output_files": "output",
            "media_folder": "media",
        }
    )
    return bash_script
