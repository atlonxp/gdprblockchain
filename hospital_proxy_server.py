import socket
import sys
from hospital import Hospital
from parser import Parser
from threading import Thread
from threading import Condition
from constants import ADDRESS
from constants import PORT
from constants import MESSAGE_SIZE
from constants import TYPE
import medical_record
import constants
import patient_msg
import phys_msg
import crypto
import card_helper

"""
Supported Commands
"""
EXIT = 'exit'
STAFF = 'staff'
DB = 'db'

h = None
parser = Parser()

def main():
    """
    Wrapper around the hospital class.
    """
    arguments = sys.argv
    if len(arguments) < 2:
        print("ERROR: missing argument - %s" %(parser.get_hosp_names_string()))
        return

    hospital_name = arguments[1]

    if not parser.valid_hosp(hospital_name):
        print("ERROR: invalid argument - %s" %(parser.get_hosp_names_string()))
        return

    # Construct patient using info. from parser.
    global h
    h = Hospital(hospital_name, parser.get_bc_contact_info()[ADDRESS], parser.get_bc_contact_info()[PORT])
    contact_info = parser.get_hosp_contact_info(hospital_name)
    address = contact_info[ADDRESS]
    port = contact_info[PORT]

    # Condition variable for clean termination.
    cv = Condition()

    # Create socket object.
    s = socket.socket()
    s.bind(('', port))
    print("Socket binded to %s" %(port))

    # Put the socket into listening mode.        
    s.listen(5)
    print("Socket is listening")

    # Spawn repl thread.
    print("Starting repl for %s." %(hospital_name))
    t = Thread(target=repl, args=(s, cv))
    t.daemon = True
    t.start()

    # Spawn connection thread.
    t = Thread(target=handle_connection, args=(s,))
    t.daemon = True
    t.start()

    # Wait for termination.
    termination = False    
    cv.acquire()
    while not termination:
        cv.wait()
        termination = True
        cv.release()

def repl(s, cv):
    print("Kicking off REPL\n\n")
    while True:
        commands = sys.stdin.readline().split()
        try:
            command = commands[0]
            if command == EXIT:
                # Close the socket.
                s.close()
                cv.acquire()
                # Notify main thread that user would like to exit.
                cv.notify()
                cv.release()
                return
            elif command == STAFF:
                print(h.get_staff())
            elif command == DB:
                print(h.get_db())
            else:
                print("Supported Commands: [" + EXIT + ", " + DB + ", " + STAFF + "]")
        except Exception, e:
            print(e)

def handle_connection(s):
    while True:
        try:
            c, addr = s.accept()
            print("Got connection from " + addr[0] + ": " + str(addr[1]))
            # Start a thread for each socket.
            t = Thread(target=listen_on_socket, args=(c,))
            t.daemon = True
            t.start()
        except Exception, e:
            #print(e)
            return

def listen_on_socket(c):
    while True:
        try:
            data = c.recv(MESSAGE_SIZE)
            if data:
                messages = constants.deserialize(data)
                for message in messages:
                    response = handle_message(message)
                    # This is a special case since we may be sending multiple blocks of encrypted data.
                    if message.get(TYPE) == patient_msg.READ:
                        if response == None:
                            # No data found for patient.
                            c.send(patient_msg.read_response_msg("", 0, False))
                        else:
                            # Send all of the blocks.
                            for r in response:
                                c.send(patient_msg.read_response_msg(r, len(response), True))
                    else:
                        c.send(response)
            else:
                return clean_up(c)
        except Exception, e:
            print(e)
            return clean_up(c)

def handle_message(message):
    type = message.get(TYPE)
    if type == patient_msg.REGISTER:
        patient_name = message.get(patient_msg.PATIENT_NAME)
        patient_id = message.get(patient_msg.PATIENT_ID)
        print("-------> Register Patient %s" %(patient_name))
        # API Call #
        card = h.register_patient(patient_name, patient_id)
        if card == None:
            # Unsuccessful registration.
            return patient_msg.register_response_msg(False)
        else:
            # Successful registration.
            card_path = parser.get_patient_card(patient_name)
            priv_key_path = parser.get_patient_priv_key_path(patient_name)
            # Store the private key.
            crypto.store_private_key(priv_key_path, card.priv_key)
            # Update card to store the location of where the private key is stored.
            card.priv_key = priv_key_path
            # Store contents of card in file.          
            f = open(card_path, "w+")
            f.write(str(card))
            f.close()
            return patient_msg.register_response_msg(True)
    elif type == phys_msg.REGISTER:
        physician_name = message.get(phys_msg.PHYSICIAN_NAME)
        physician_id = message.get(phys_msg.PHYSICIAN_ID)
        print("-------> Register Physician %s" %(physician_name))
        # API Call #
        response = h.register_physician(physician_name, physician_id)
        if response:
            return phys_msg.register_response_msg(True)
        else:
            return phys_msg.register_response_msg(False)
    elif type == phys_msg.WRITE:
        physician_id = message.get(phys_msg.PHYSICIAN_ID)
        med_rec_string = message.get(phys_msg.MEDICAL_RECORD)
        card_path = message.get(phys_msg.CARD_PATH)
        # Convert params into objects.
        card = card_helper.get_card_object(card_path)
        med_rec = medical_record.get_medical_record(med_rec_string)
        print("-------> Write Request")
        response = h.write(card, med_rec, physician_id)
        if response:
            return phys_msg.write_response_msg(True)
        else:
            return phys_msg.write_response_msg(False)
    elif type == patient_msg.READ:
        card_uid = message.get(patient_msg.CARD_UID)
        print("-------> Read Request")
        blocks = h.read(card_uid)
        return blocks
    else:
        print("ERROR: unknown type %s" %(type))

def clean_up(c):
    print("Closing connection")
    c.close()

main()
    