from django.core.management import call_command
from django.conf import settings
from catmaid.control.cropping import cleanup as cropping_cleanup, process_crop_job
from catmaid.control.nat import export_skeleton_as_nrrd_async
from catmaid.control.treenodeexport import process_export_job
from catmaid.control.roi import create_roi_image
from catmaid.control.node import update_node_query_cache as do_update_node_query_cache
from catmaid.control.floodfilling import flood_fill_async
from celery import shared_task


@shared_task
def cleanup_cropped_stacks():
    """Define a periodic task that runs every day at midnight. It removes all
    cropped stacks that are older than 24 hours.
    """
    seconds_per_day = 60 * 60 * 24
    cropping_cleanup(seconds_per_day)
    return "Cleaned cropped stacks directory"


@shared_task
def update_project_statistics():
    """Call management command to update all project statistics
    """
    call_command('catmaid_populate_summary_tables')
    return "Updated project statistics summary"


@shared_task
def update_node_query_cache():
    """Update the query cache of changed sections for node providers defined in
    the NODE_PROVIDERS settings variable.
    """
    do_update_node_query_cache()
    return "Updating node query cache"
