from cloud_fn_utilities.gcp.compute_manager import ComputeManager


def sample_set_metadata():
    # Create a client
    client = ComputeManager.InstancesClient()

    # Initialize request argument(s)
    request = ComputeManager.SetMetadataInstanceRequest(
        instance="instance_value",
        project="project_value",
        zone="zone_value",
    )

    # Make the request
    response = client.set_metadata(request=request)

    # Handle the response
    print(response)