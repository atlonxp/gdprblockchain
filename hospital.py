import crypto
from hasher import hash
from medical_record import MedicalRecord
from time import time
import csv

class Hospital:
    def __init__(self, name, blockchain, staff):
        self.name = name
        self.blockchain = blockchain
        self.db = dict()
        self.address = None
        self.port = None
        self.staff = staff

    def register_physician(self, uid):
        if uid in self.staff:
            return True
        print("ERROR: physician not a registered staff member")
        return False

    def register_patient(self, name, patient_id):
        # Generate uid from patient credentials.
        uid = name + patient_id
        hash_uid = hash(uid)
        # Check if uid resides on public blockchain.
        if self.blockchain.contains_hash_id(hash_uid):
            print("ERROR: patient affiliated with another hospital")
            return None
        # Generate priv/pub key pairs for new patient in hospital ecosystem.
        priv_key, pub_key = crypto.generate_keys()
        # Update public blockchain.
	self.add_to_blockchain(hash_uid, pub_key);
        # Populate medical record with patient information.
        medical_record = self.create_first_med_record(name, patient_id)
        # Insert into hospital k,v store.
        self.insert(uid, pub_key, medical_record)
	return Card(uid, priv_key, self.name)

    def write(self, card, medical_record):
        # Confirm that requester is authorized to write to this hospital's db.
        if card.hospital_name != self.name:
            print("ERROR: invalid request to write")
            return False
        # Obtain the hash index. 
        hash_id = hash(card.uid)
        # Get the public key from the public blockchain.
        block = self.blockchain.get_block(hash_id)
        pub_key = block.pub_key
        # Hospital db key.
        hosp_db_key = crypto.encrypt(card.uid, pub_key)
        # Validate the request by checking that the decrypted_db_key using
        # the private key is equal to the uid.
        if self.valid_request(hosp_db_key, card):
            most_recent_write = self.get_last_block(hosp_db_key)
            if most_recent_write:
                most_recent_write = self.deconstruct(crypto.decrypt(most_recent_write, card.priv_key))
                current = self.deconstruct(str(medical_record))
                merged = self.merge(most_recent_write, current)
                self.insert(card.uid, card.priv_key, merged)
                return True
            else:
                print("ERROR: Couldn't find block associated with key")
                return False
        else:
            print("ERROR: Private key does not correspond to public key")
            return False
    
    def read(self, card):

            
    def valid_request(self, encrypted_val, card):
        uid = crypto.decrypt(encrypted_val, card.priv_key)
        if uid == card.uid:
            return True
        return False

    def merge(self, prev, curr):
        for k,v in curr.items():
            if v == 'None':
                curr.update({k: prev.get(k)})
        return curr
    
    def get_last_block(self, hosp_db_key):
        if hosp_db_key in self.db:
            blocks = self.db.get(hosp_db_key)
            blocks = blocks.split(",")
            block = blocks[len(blocks) - 1]
            return block
        else:
            return None

    def add_to_blockchain(self, hash_uid, pub_key):
	self.blockchain.new_transaction(hash_uid, pub_key);
	self.blockchain.mine()

    def create_first_med_record(self, name, patient_id):
        med_record = MedicalRecord()
        med_record.name = name
        med_record.patient_id = patient_id
        med_record.hospital = self.name
        med_record.date = time()
        med_record.notes = ""
        med_record.signature = self.name
        return med_record

    def deconstruct(self, med_record):
        med_record = med_record.split(",")
        n = dict()        
        for m in med_record:
            m = m.split(":")
            n.update({m[0]: m[1]})
        return(n)
            
    def insert(self, uid, public_key, medical_record):
        key = crypto.encrypt(uid, public_key)
        value = crypto.encrypt(str(medical_record), public_key)
        if key in self.db:
            self.db.get(key) + "," + value
        else:
            self.db.update({key: value})         

    def clean_up(self):
        self.db.close()

class Card:
    def __init__(self, uid, priv_key, name):
        self.uid = uid
        self.priv_key = priv_key
        self.hospital_name = name

    def update(self, hospital_id):
        self.hospital_id = hospital_id

