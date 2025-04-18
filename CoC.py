#!/usr/bin/env python3
import os
import struct
import argparse
import base64
from Crypto.Cipher import AES
import uuid
import hashlib
import maya
import sys

# Constants
BLOCKCHAIN_FILE = os.getenv("BCHOC_FILE_PATH", "bchocBlockchain.bin")
AES_KEY = b"R0chLi4uLi4uLi4="
PASSWORDS = {
    "P80P": "POLICE",
    "L76L": "LAWYER",
    "A65A": "ANALYST",
    "E69E": "EXECUTIVE",
    "C67C": "CREATOR",
}

# Block Structure Format
BLOCK_FORMAT = "32s d 32s 32s 12s 12s 12s I"
BLOCK_SIZE = struct.calcsize(BLOCK_FORMAT)

def encryptData(data: bytes) -> bytes:
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    paddedData = data.ljust(16, b'\0')
    encrypted = cipher.encrypt(paddedData)
    #print(f"Encrypted data: {encrypted.hex()}")
    return encrypted
    
def decryptData(data: bytes) -> bytes:
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    #print(f"Attempting to decrypt: {data[:16].hex()}")
    strippedData = data.rstrip(b'\0')
    decryptedData = cipher.decrypt(strippedData)  # Decrypt only the first 16 bytes
    #print(f"Decrypted bytes: {decryptedData.hex()}")
    return decryptedData.rstrip(b'\0')  # Remove padding
    
def hashBlock(prevHash, unixTimestamp, caseId, itemId, state, creator, owner, data):
    blockContent = struct.pack(BLOCK_FORMAT, prevHash, unixTimestamp, caseId, itemId, state, creator, owner, data)
    return hashlib.sha256(blockContent).digest()
    
def padBytes(s, length):
    """Pads the string 's' to the specified byte length using null bytes."""
    return s.encode("utf-8").ljust(length, b"\0")

def createGenesisBlock():
    """Creates the genesis block."""
    prevHash = b"0" * 32
    unixTimestamp = 0.0
    caseId = b"0" * 32
    evidenceId = b"0" * 32
    state = padBytes("INITIAL", 12)
    creator = b"\0" * 12
    owner = b"\0" * 12
    data = b"Initial block\0"
    dataLength = len(data)
    packed = struct.pack(
        BLOCK_FORMAT, prevHash, unixTimestamp, caseId, evidenceId, state, creator, owner, dataLength
    )
    return packed + data

def initBlockchain():
    """Initializes the blockchain with the genesis block."""
    if os.path.exists(BLOCKCHAIN_FILE):
        print("Blockchain file found with INITIAL block.")
        return
    with open(BLOCKCHAIN_FILE, "wb") as f:
        genesisBlock  = createGenesisBlock()  # Use the create_genesis_block() to get the genesis block
        f.write(genesisBlock)
        print("Blockchain file not found. Created INITIAL block.")
        #print(f"Block size: {len(genesisBlock)}")
        
def addCase(caseId, itemIds, creator, password):
    if password not in PASSWORDS.keys():
        print("Invalid password")
        os._exit(1)
    
    try:
        uuid.UUID(caseId)  # Validate caseId format
    except ValueError:
        print("Invalid case ID format.")
        os._exit(1)

    caseId = encryptData(uuid.UUID(caseId).bytes)
    creator = creator.encode().ljust(12, b'\0')
    owner = creator
    prevHash = b"0"*32
    data = b""
    dataLength = len(data)
    
    with open(BLOCKCHAIN_FILE, "ab") as f:
        for itemId in itemIds:
            try:
                int(itemId)  # Validate itemId is an integer
            except ValueError:
                print(f"Invalid item ID: {itemId}")
                continue
                
            itemBytes = struct.pack("I", int(itemId))
            evidenceId = encryptData(itemBytes)
            timestamp = maya.now().datetime(to_timezone='UTC')
            unixTimestamp = timestamp.timestamp()
            formattedTimestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            state = b"CHECKEDIN\0\0\0"
            
            block = struct.pack(BLOCK_FORMAT, prevHash, unixTimestamp, caseId, evidenceId.ljust(32, b'\0'), state, creator, owner, dataLength)
            f.write(block)
            print(f"> Added item: {itemId}")
            print(f"> Status: CHECKEDIN")
            print(f"> Time of action: {formattedTimestamp}")

def showHistory(itemId, password=None):
    authorized = password in PASSWORDS if password else False
    targetItemId = int(itemId)  # Convert input itemId to integer for comparison

    with open(BLOCKCHAIN_FILE, "rb") as f:
        found = False
        while True:
            blockData = f.read(BLOCK_SIZE)
            
            if len(blockData) == 0:
                break  # End of file reached
                
            if len(blockData) < BLOCK_SIZE:
                print(f"Warning: Incomplete block, skipping (length: {len(blockData)})")
                continue  # Skip incomplete blocks
            
            #print(f"block data: {blockData}")
            prevHash, timestamp, caseId, itemId, state, creator, owner, dataLength = struct.unpack(BLOCK_FORMAT, blockData)
            
            # Skip over the variable-length data section
            # This can be done by using `f.seek()` to move the file pointer forward by `dataLength` bytes
            f.seek(dataLength, os.SEEK_CUR)  # Skipping the `dataLength` part
            
            #print(f"Encrypted evidenceId: {itemId.hex()}")
            try:
                decryptedBytes = decryptData(itemId)
            	#print(f"Unpacking first 4 bytes: {decryptedBytes[:4].hex()}")
                decryptedId = struct.unpack("I", decryptedBytes[:4])[0]  # Unpack first 4 bytes
            	#print(f"Decrypted evidence ID: {decryptedId}")
            except Exception:
                print(f"Decryption/unpacking failed:")
                decryptedId = -1  # Failed decryption
                
            #print(f"decrypted evidence id: {decryptedId}")
            #print(f"item id: {itemId}")
            #print(f"item id length: {len(itemId)}")
            if decryptedId == targetItemId:
                found = True
                # Format timestamp as YYYY-MM-DDTHH:MM:SS.ssssssZ
                formatted_time = maya.MayaDT(timestamp).datetime(to_timezone='UTC').strftime('%Y-%m-%dT%H:%M:%S.%fZ')

                if authorized:
                    try:
                        caseIdStr = str(uuid.UUID(bytes=decryptData(caseId)))
                    except Exception:
                        caseIdStr = "<invalid case ID>"
                else:
                    caseIdStr = caseId.rstrip(b'\x00').hex()
                    decryptedId = itemId.rstrip(b'\x00').hex()

                action = state.decode().strip()
                
                print(f"> Case: {caseIdStr}")
                print(f"> Item: {decryptedId}")
                print(f"> Action: {action}")
                print(f"> Time: {formatted_time}")

        if not found:
            print("> No history found for that item.")

def showItems(caseId, password):
    """Displays all items corresponding to the given case ID, if the password matches an owner's password."""
    authorized = password in PASSWORDS if password else False
    try:
        targetCaseId = uuid.UUID(caseId).bytes if authorized else caseId
    except ValueError:
        print("Invalid case ID format.")
        os._exit(1)

    found = False
    items = []

    with open(BLOCKCHAIN_FILE, "rb") as f:
        while True:
            blockData = f.read(BLOCK_SIZE)
            if len(blockData) == 0:
                break
            if len(blockData) < BLOCK_SIZE:
                print(f"Warning: Incomplete block, skipping (length: {len(blockData)})")
                continue
            prevHash, timestamp, caseId, itemId, state, creator, owner, dataLength = struct.unpack(BLOCK_FORMAT, blockData)
            f.seek(dataLength, os.SEEK_CUR)

            # Compare case ID
            if authorized:
                #print("Inside authorized");
                try:
                    #print("test: {targetCaseId}")
                    decryptedCaseId = decryptData(caseId)
                    if decryptedCaseId == targetCaseId:
                        try:
                            decryptedItemId = struct.unpack("I", decryptData(itemId)[:4])[0]
                            items.append({
                                'itemId': decryptedItemId,
                                'caseId': str(uuid.UUID(bytes=decryptedCaseId)),
                                'state': state.decode().strip(),
                                'timestamp': maya.MayaDT(timestamp).datetime(to_timezone='UTC').strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                            })
                            found = True
                        except Exception:
                            continue
                except Exception:
                    continue
            else:
                # For unauthorized users, compare encrypted case ID (hex)
                if caseId.rstrip(b'\x00').hex() == targetCaseId:
                    try:
                        decryptedItemId = itemId.rstrip(b'\x00').hex()
                        items.append({
                            'itemId': decryptedItemId,
                            'caseId': caseId.rstrip(b'\x00').hex(),
                            'state': state.decode().strip(),
                            'timestamp': maya.MayaDT(timestamp).datetime(to_timezone='UTC').strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                        })
                        found = True
                    except Exception:
                        continue

    if not found:
        print("> No items found for that case.")
        return

    # Print items
    for item in items:
        print(f"> Case: {item['caseId']}")
        print(f"> Item: {item['itemId']}")
        print(f"> Action: {item['state']}")
        print(f"> Time: {item['timestamp']}")

def checkin_item(itemId, password):
    """Adds a new checkin entry to the chain of custody for the given evidence item."""
    if password not in PASSWORDS:
        print("Invalid password")
        os._exit(1)

    targetItemId = int(itemId)
    latestBlock = None

    # Read blockchain to find the most recent block for the item
    with open(BLOCKCHAIN_FILE, "rb") as f:
        while True:
            blockData = f.read(BLOCK_SIZE)
            if len(blockData) == 0:
                break
            if len(blockData) < BLOCK_SIZE:
                print(f"Warning: Incomplete block, skipping (length: {len(blockData)})")
                continue
            prevHash, timestamp, caseId, itemId, state, creator, owner, dataLength = struct.unpack(BLOCK_FORMAT, blockData)
            f.seek(dataLength, os.SEEK_CUR)
            try:
                decryptedBytes = decryptData(itemId)
                decryptedId = struct.unpack("I", decryptedBytes[:4])[0]
            except Exception:
                decryptedId = -1
            if decryptedId == targetItemId:
                # Store the most recent block (based on timestamp)
                if latestBlock is None or timestamp > latestBlock['timestamp']:
                    latestBlock = {
                        'caseId': caseId,
                        'owner': owner,
                        'state': state.decode('utf-8').rstrip('\0'),
                        'timestamp': timestamp
                    }

    if latestBlock is None:
        print(f"Item {targetItemId} not found in blockchain.")
        os._exit(1)

    # Check if the item is already checked in
    if latestBlock['state'] == "CHECKEDIN":
        print(f"Item {targetItemId} is already checked in.")
        os._exit(1)

    # Create new checkin block
    timestamp = maya.now().datetime(to_timezone='UTC')
    unixTimestamp = timestamp.timestamp()
    formattedTimestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    state = b"CHECKEDIN\0\0\0"
    itemBytes = struct.pack("I", targetItemId)
    evidenceId = encryptData(itemBytes)
    caseId = latestBlock['caseId']
    owner = latestBlock['owner']
    creator = owner
    data = b""
    dataLength = len(data)
    prevHash = b"0"*32

    # Decrypt caseId for output
    try:
        caseIdStr = str(uuid.UUID(bytes=decryptData(caseId)))
    except Exception:
        caseIdStr = "<invalid case ID>"

    with open(BLOCKCHAIN_FILE, "ab") as f:
        block = struct.pack(BLOCK_FORMAT, prevHash, unixTimestamp, caseId, evidenceId.ljust(32, b'\0'), state, creator, owner, dataLength)
        f.write(block)
    
    print(f"> Case: {caseIdStr}")
    print(f"> Checked in item: {targetItemId}")
    print(f"> Status: CHECKEDIN")
    print(f"> Time of action: {formattedTimestamp}")
    
def checkout_item(itemId, password):
    """Adds a new checkout entry to the chain of custody for the given evidence item."""
    if password not in PASSWORDS:
        print("Invalid password")
        os._exit(1)

    targetItemId = int(itemId)
    latestBlock = None

    # Read blockchain to find the most recent block for the item
    with open(BLOCKCHAIN_FILE, "rb") as f:
        while True:
            blockData = f.read(BLOCK_SIZE)
            if len(blockData) == 0:
                break
            if len(blockData) < BLOCK_SIZE:
                print(f"Warning: Incomplete block, skipping (length: {len(blockData)})")
                continue
            prevHash, timestamp, caseId, itemId, state, creator, owner, dataLength = struct.unpack(BLOCK_FORMAT, blockData)
            f.seek(dataLength, os.SEEK_CUR)
            try:
                decryptedBytes = decryptData(itemId)
                decryptedId = struct.unpack("I", decryptedBytes[:4])[0]
            except Exception:
                decryptedId = -1
            if decryptedId == targetItemId:
                # Store the most recent block (based on timestamp)
                if latestBlock is None or timestamp > latestBlock['timestamp']:
                    latestBlock = {
                        'caseId': caseId,
                        'owner': owner,
                        'state': state.decode('utf-8').rstrip('\0'),
                        'timestamp': timestamp
                    }

    if latestBlock is None:
        print(f"Item {targetItemId} not found in blockchain.")
        os._exit(1)

    # Check if the item is not checked in
    if latestBlock['state'] != "CHECKEDIN":
        print(f"Item {targetItemId} is not checked in.")
        os._exit(1)

    # Create new checkout block
    timestamp = maya.now().datetime(to_timezone='UTC')
    unixTimestamp = timestamp.timestamp()
    formattedTimestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    state = b"CHECKEDOUT\0\0"
    itemBytes = struct.pack("I", targetItemId)
    evidenceId = encryptData(itemBytes)
    caseId = latestBlock['caseId']
    owner = latestBlock['owner']
    creator = owner
    data = b""
    dataLength = len(data)
    prevHash = b"0"*32

    # Decrypt caseId for output
    try:
        caseIdStr = str(uuid.UUID(bytes=decryptData(caseId)))
    except Exception:
        caseIdStr = "<invalid case ID>"

    with open(BLOCKCHAIN_FILE, "ab") as f:
        block = struct.pack(BLOCK_FORMAT, prevHash, unixTimestamp, caseId, evidenceId.ljust(32, b'\0'), state, creator, owner, dataLength)
        f.write(block)
    
    print(f"> Case: {caseIdStr}")
    print(f"> Checked out item: {targetItemId}")
    print(f"> Status: CHECKEDOUT")
    print(f"> Time of action: {formattedTimestamp}")

# Main function
def main():
    if len(sys.argv) < 2:
        print("> No command provided.")
        return

    cmd = sys.argv[1]

    if cmd == "init":
        initBlockchain()

    elif cmd == "add":
        parser = argparse.ArgumentParser()
        parser.add_argument("-c", "--caseId", required=True)
        parser.add_argument("-i", "--itemId", action='append', required=True, help="Item ID (can be specified multiple times)")
        parser.add_argument("-g", "--creator", required=True)
        parser.add_argument("-p", "--password", required=True)
        args = parser.parse_args(sys.argv[2:])
        addCase(args.caseId, args.itemId, args.creator, args.password)

    elif cmd == "show" and len(sys.argv) > 2 and sys.argv[2] == "history":
        parser = argparse.ArgumentParser()
        parser.add_argument("-i", "--itemId", required=True)
        parser.add_argument("-p", "--password", required=False)
        args = parser.parse_args(sys.argv[3:])
        showHistory(args.itemId, args.password)
        
    elif cmd == "show" and len(sys.argv) > 2 and sys.argv[2] == "items":
        parser = argparse.ArgumentParser()
        parser.add_argument("-c", "--caseId", required=True)
        parser.add_argument("-p", "--password", required=True)
        args = parser.parse_args(sys.argv[3:])
        showItems(args.caseId, args.password)

    elif cmd == "checkout":
        parser = argparse.ArgumentParser()
        parser.add_argument("-i", "--itemId", required=True)
        parser.add_argument("-p", "--password", required=True)
        args = parser.parse_args(sys.argv[2:])
        checkout_item(args.itemId, args.password)

    elif cmd == "checkin":
        parser = argparse.ArgumentParser()
        parser.add_argument("-i", "--itemId", required=True)
        parser.add_argument("-p", "--password", required=True)
        args = parser.parse_args(sys.argv[2:])
        checkin_item(args.itemId, args.password)

    else:
        print("> Invalid command.")


if __name__ == "__main__":
    main()
