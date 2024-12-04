import pandas as pd
import mysql.connector

# Establishing database connection
try:
    conn = mysql.connector.connect(
        user='mhaapala',
        password='365-fall24-028148594',
        host='mysql.labthreesixfive.com',
        database='mhaapala'
    )
except mysql.connector.Error as err:
    print(f"Error: {err}")
    exit()

def main():
    print("Braeden Alonge, Miro Haapalainen - Lab 7")
    while True:
        print("\nSelect an option:")
        print("1. Rooms and Rates")
        print("2. Reservations")
        print("3. Reservation Cancellation")
        print("4. Detailed Reservation Information")
        print("5. Revenue")
        command = input("Enter command (or 'exit' to quit): ").strip()

        if command == "1":  # Rooms and Rates
            RoomsAndRates()
        elif command == "2":  # Reservations
            Reservations()
        elif command == "3":  # Reservation Cancellation
            print("Feature not implemented yet.")
        elif command == "4":  # Detailed Reservation Information
            print("Feature not implemented yet.")
        elif command == "5":  # Revenue
            print("Feature not implemented yet.")
        elif command.lower() == "exit":
            print("Goodbye!")
            break
        else:
            print("Invalid option. Try again.")

def RoomsAndRates():
    """Retrieve room popularity and availability data."""
    try:
        query = """
            SELECT
                r.RoomCode, r.RoomName,
                COALESCE(rp.PopularityScore, 0.0) AS PopularityScore,
                COALESCE(nac.NextAvailableCheckIn, CURRENT_DATE) AS NextAvailableCheckIn
            FROM lab7_rooms r
            LEFT JOIN (
                SELECT Room, 
                    ROUND(SUM(DATEDIFF(LEAST(Checkout, CURRENT_DATE),
                        GREATEST(CheckIn, DATE_SUB(CURRENT_DATE, INTERVAL 180 DAY))) / 180), 2) AS PopularityScore
                FROM lab7_reservations
                WHERE CheckIn <= CURRENT_DATE
                  AND Checkout >= DATE_SUB(CURRENT_DATE, INTERVAL 180 DAY)
                GROUP BY Room
            ) rp ON r.RoomCode = rp.Room
            LEFT JOIN (
                SELECT Room, MAX(Checkout) AS NextAvailableCheckIn
                FROM lab7_reservations
                WHERE Checkout <= CURRENT_DATE
                GROUP BY Room
            ) nac ON r.RoomCode = nac.Room
            ORDER BY PopularityScore DESC;
        """
        df = pd.read_sql(query, conn)
        print("\n--- Rooms and Rates ---")
        print(df)
    except Exception as e:
        print(f"Error retrieving room data: {e}")

def Reservations():
    """Handle reservation creation."""
    try:
        # Gather reservation details
        fname = input("First Name: ").strip()
        lname = input("Last Name: ").strip()
        room = input("Room Code (or 'Any'): ").strip()
        bed_type = input("Bed Type (or 'Any'): ").strip()
        start_date = input("Start Date (YYYY-MM-DD): ").strip()
        end_date = input("End Date (YYYY-MM-DD): ").strip()
        adults = int(input("Number of Adults: "))
        kids = int(input("Number of Children: "))
        guests = adults + kids

        # Query for available rooms
        query = """
            SELECT r.RoomCode, r.RoomName, r.bedType, r.basePrice
            FROM lab7_rooms r
            WHERE r.maxOcc >= {guests}
              AND (r.RoomCode = '{room}' OR '{room}' = 'Any')
              AND (r.bedType = '{bed_type}' OR '{bed_type}' = 'Any')
              AND NOT EXISTS (
                  SELECT 1
                  FROM lab7_reservations res
                  WHERE res.Room = r.RoomCode
                    AND res.CheckIn < '{end_date}' 
                    AND res.Checkout > '{start_date}'
              );
        """
        df = pd.read_sql(query, conn)
        if df.empty:
            print("No available rooms for the specified criteria.")
        else:
            print("Available Rooms:")
            print(df)
            # Handle room selection and booking here...
    except Exception as e:
        print(f"Error processing reservation: {e}")

if __name__ == "__main__":
    main()