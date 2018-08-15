# -*- coding: utf-8 -*-
import subprocess

from pathlib import Path

from django.conf import settings
from django.http import JsonResponse

from catmaid.control.compute_server import get_server
from catmaid.control.authentication import requires_user_role
from catmaid.models import Message, User, UserRole
from catmaid.control.message import notify_user

from celery.task import task

from rest_framework.decorators import api_view

import time


# The path were server side exported files get stored in
output_path = Path(settings.MEDIA_ROOT, settings.MEDIA_EXPORT_SUBDIRECTORY)


@api_view(["POST"])
@requires_user_role(UserRole.Browse)
def flood_fill_skeleton(request, project_id):
    """
    Flood fill a skeleton. Necessary information:
    Server configuration
    volume toml
    model toml
    skeleton csv
    model hdf5
    """

    server = {
        "id": request.POST.get("compute_server"),
        "diluvian_path": request.POST.get("server_diluvian_path"),
        "env_source": request.POST.get("server_env_source"),
    }

    server["address"] = get_server(server["id"])["address"]

    # the name of the temporary directory used for files
    # related to flood filling
    job_name = request.POST.get("job_name")

    # If the temporary directory doesn't exist, create it
    media_folder = Path(settings.MEDIA_ROOT)
    if not (media_folder / job_name).exists():
        (media_folder / job_name).mkdir()
    local_temp_der = media_folder / job_name

    # Create a copy of the files sent in the request in the
    # temporary directory so that it can be copied with scp
    # in the async function
    for f in request.FILES.values():
        file_path = local_temp_der / f.name
        file_path.write_text(f.read().decode("utf-8"))

    # HARD-CODED SETTINGS
    # TODO: move these to appropriate locations
    ssh_key_path = settings.SSH_KEY_PATH
    model_file = "trained_models/pattonw-v0/pattonw-v0.hdf5"  # widget settings
    output_file_name = "output_file"  # widget settings
    server_async_dir = "holding_dir/"
    server_job_dir = job_name  # widget settings

    # Flood filling async function
    x = flood_fill_async.delay(
        request.user.id,
        ssh_key_path,
        local_temp_der,
        server,
        server_async_dir,
        server_job_dir,
        model_file,
        output_file_name,
    )

    # Send a response to let the user know the async funcion has started
    return JsonResponse({"success": True})


@task()
def flood_fill_async(
    user_id,
    ssh_key_path,
    local_temp_der,
    server,
    server_async_dir,
    server_job_dir,
    model_file,
    output_file_name,
):
    time.sleep(60)
    return 4

    setup = "scp -i {ssh_key_path} -pr {local_dir} {server_address}:{server_diluvian_dir}/{server_async_dir}".format(
        **{
            "local_dir": local_temp_der,
            "server_address": server["address"],
            "server_diluvian_dir": server["diluvian_path"],
            "server_async_dir": server_async_dir,
            "ssh_key_path": ssh_key_path,
        }
    )
    files = {}
    for f in local_temp_der.iterdir():
        files[f.name.split(".")[0]] = Path(
            "~/", server["diluvian_path"], server_async_dir, server_job_dir, f.name
        )

    flood_fill = """
    ssh -i {ssh_key_path} {server}
    source {server_ff_env_path}
    cd  {server_diluvian_dir}
    python -m diluvian skeleton-fill-parallel -s {skeleton_file} -m {model_file} -c {config_file} -v {volume_file} --no-in-memory -l INFO --max-moves 3
    """.format(
        **{
            "server": server["address"],
            "server_ff_env_path": server["env_source"],
            "server_diluvian_dir": server["diluvian_path"],
            "skeleton_file": files["skeleton"],
            "model_file": model_file,
            "config_file": files["config"],
            "volume_file": files["volume"],
            "ssh_key_path": ssh_key_path,
        }
    )

    cleanup = """
    scp -i {ssh_key_path} {server}:{server_diluvian_dir}/{output_file_name}.npy {local_temp_der}
    ssh -i {ssh_key_path} {server}
    rm  {server_diluvian_dir}/{output_file_name}.npy
    rm -r {server_diluvian_dir}/{server_async_dir}/{server_job_dir}
    """.format(
        **{
            "server": server["address"],
            "server_diluvian_dir": server["diluvian_path"],
            "local_temp_der": local_temp_der,
            "output_file_name": output_file_name,
            "ssh_key_path": ssh_key_path,
            "server_async_dir": server_async_dir,
            "server_job_dir": server_job_dir,
        }
    )

    print(setup)

    process = subprocess.Popen(
        "/bin/bash", stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding="utf8"
    )
    out, err = process.communicate(setup)
    print(out)

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