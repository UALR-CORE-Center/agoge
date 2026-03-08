from main_app_v3.backend.core.workout_internet_firewall import WorkoutInternetFirewall


if __name__ == "__main__":
    print(f"Workout Internet Firewall Tester.")

    test_workout_id = str(input(f"Which workout do you want to test? "))
    internet_firewall = WorkoutInternetFirewall(workout_id=test_workout_id)
    internet_firewall.add_ip_address("64.127.134.253")
    internet_firewall.disable_internet_access()
