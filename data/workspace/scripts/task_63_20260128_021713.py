import platform
import sys


def show_host_os():
    """Display host operating system information"""
    try:
        # Get basic OS information
        os_name = platform.system()
        os_release = platform.release()
        os_version = platform.version()

        # Get detailed platform information
        platform_info = platform.platform()

        # Display results
        print(f"Operating System: {os_name}")
        print(f"Release: {os_release}")
        print(f"Version: {os_version}")
        print(f"Platform: {platform_info}")

    except Exception as e:
        print(f"Error retrieving OS information: {e}")
        sys.exit(1)


if __name__ == "__main__":
    show_host_os()
