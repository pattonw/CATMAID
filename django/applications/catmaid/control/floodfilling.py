# -*- coding: utf-8 -*-

import os
import subprocess

from pathlib import Path

from datetime import datetime

from django.conf import settings
from django.http import JsonResponse, HttpResponse

from catmaid.control.common import get_request_bool, urljoin
from catmaid.control.authentication import requires_user_role
from catmaid.models import Message, User, UserRole
from catmaid.control.message import notify_user

from celery.task import task

from rest_framework.authtoken.models import Token

import time


# The path were server side exported files get stored in
output_path = Path(settings.MEDIA_ROOT, settings.MEDIA_EXPORT_SUBDIRECTORY)


# @requires_user_role(UserRole.Annotate)
def flood_fill_skeleton(request):
    """
    Flood fill a skeleton. Necessary information:
    Server configuration
    volume toml
    model toml
    skeleton csv
    model hdf5
    """

    # the name of the temporary directory used for files
    # related to flood filling
    temp_dir_name = "ff_temp"

    # If the temporary directory doesn't exist, create it
    media_folder = Path(settings.MEDIA_ROOT)
    if not (media_folder / temp_dir_name).exists():
        (media_folder / temp_dir_name).mkdir()
    temp_dir = media_folder / temp_dir_name

    # Create a copy of the files sent in the request in the
    # temporary directory so that it can be copied with scp
    # in the async function
    for f in request.FILES.values():
        file_path = temp_dir / f.name
        print(f.name)
        print(f.read().decode("utf-8"))
        file_path.write_text(f.read().decode("utf-8"))

    # The server to run the flood filling
    # This information should probably be put in a table
    server = settings.GPU_SERVER
    server_diluvian_dir = "code/diluvian"
    server_env_path = ".virtualenv/cardona-gpu1-py35-tf18/bin/activate"

    # flood_fill_async.delay(request.user.id)

    return JsonResponse({"success": True})


@task()
def flood_fill_async(
    user_id,
    temp_dir,
    server="cardona-gpu1.int.janelia.org",
    diluvian_dir="code/diluvian",
    env_path=".virtualenv/cardona-gpu1-py35-tf18/bin/activate",
    model_file="trained_models/pattonw-v0/pattonw-v0.hdf5",
    output_file_name="output_file",
    server_temp_dir = "holding_dir"
):

    # TODO: Setup, i.e. scp the files onto the server.
    setup = ""
    files = {}
    for f in temp_dir.iterdir():
        files[f.name.split('.')[0]] = Path(diluvian_dir,server_temp_dir)
        setup = (
            setup
            + "scp {file_path} {gpu_server}:{diluvian_dir}/{server_temp_dir}\n".format(
                **{
                    "file_path": str(f),
                    "gpu_server": server,
                    "diluvian_dir": diluvian_dir,
                    "server_temp_dir": server_temp_dir,
                }
            )
        )

    flood_fill = """
    ssh {server}
    source {env_path}
    cd  {diluvian_dir}
    python -m diluvian skeleton-fill-parallel -s {skeleton_file} -m {model_file} -c {config_file} -v {volume_file} --no-in-memory -l INFO --max-moves 3
    """.format(
        **{
            "server": server,
            "env_path": env_path,
            "diluvian_dir": diluvian_dir,
            "skeleton_file": files['skeleton'],
            "model_file": model_file,
            "config_file": files['config'],
            "volume_file": files['volume'],
        }
    )
    cleanup = """
    scp {server}:{diluvian_dir}/{output_file_name}.npy {temp_dir}
    ssh {server}
    rm  {diluvian_dir}/{output_file_name}.npy
    """.format(
        **{
            "server": server,
            "diluvian_dir": diluvian_dir,
            "temp_dir": temp_dir,
            "output_file_name": output_file_name,
        }
    )

    process = subprocess.Popen(
        "/bin/bash", stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding="utf8"
    )
    out, err = process.communicate(flood_fill)
    print(out)
    process = subprocess.Popen(
        "/bin/bash", stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding="utf8"
    )
    out, err = process.communicate(cleanup)
    print(out)

    if True:
        msg = Message()
        msg.user = User.objects.get(pk=int(user_id))
        msg.read = False

        msg.title = "ASYNC JOB MESSAGE HERE"
        msg.text = "IM DOING SOME STUFF, CHECK IT OUT"
        msg.action = "localhost:8000"

        notify_user(user_id, msg.id, msg.title)

    return "new hello world!"


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
