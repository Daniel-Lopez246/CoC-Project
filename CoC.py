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
	strippedData = data.rstrip(b'\0')
	#print(f"Attempting to decrypt: {strippedData.hex()}")
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
		
def addCase(caseId, itemId, creator, password):
	if password not in PASSWORDS:
		print("Invalid password")
		os._exit(1)
	caseId = encryptData(uuid.UUID(caseId).bytes)
	itemBytes = struct.pack("I", int(itemId))  # Pack as 4-byte integer
	#print(f"Item ID bytes before encryption: {itemBytes.hex()}")
	evidenceId = encryptData(itemBytes)
	timestamp = maya.now().datetime(to_timezone='UTC')  # Get UTC time
	unixTimestamp = timestamp.timestamp()  # This is a float representing the Unix timestamp
	formattedTimestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%fZ')  # Formatting to the required format
	state = b"CHECKEDIN\0\0\0"
	creator = creator.encode().ljust(12, b'\0')
	owner = creator
	data = b""
	dataLength = len(data)
	prevHash = b"0"*32
	with open(BLOCKCHAIN_FILE, "ab") as f:
		block = struct.pack(BLOCK_FORMAT, prevHash, unixTimestamp, caseId, evidenceId.ljust(32, b'\0'), state, creator, owner, dataLength)
		f.write(block)
	print(f"Added item: {itemId}\nStatus: CHECKEDIN\nTime of action: {formattedTimestamp}")
	#print(f"Block size: {len(block)}")

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
				continue  # Skip incomplete blocks
			
			#print(f"block data: {blockData}")
			prevHash, timestamp, caseId, itemId, state, creator, owner, dataLength = struct.unpack(BLOCK_FORMAT, blockData)
			
			# Skip over the variable-length data section
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
				formattedTime = maya.MayaDT(timestamp).datetime(to_timezone='UTC').strftime('%Y-%m-%dT%H:%M:%S.%fZ')

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
				print(f"> Time: {formattedTime}")

		if not found:
			print("> No history found for that item.")

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
		parser.add_argument("-i", "--itemId", required=True)
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


if __name__ == "__main__":
	main()
