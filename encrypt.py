import sys, os, struct, argparse, hashlib, json
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

def encrypt_file(key, in_filename, out_dir="", out_filename=None, chunksize=64*1024):
    """ Encrypts a file using AES (CBC mode) with the
        given key.

        Adopted from Eli Bendersky's example:
        http://eli.thegreenplace.net/2010/06/25/aes-encryption-of-files-in-python-with-pycrypto/

        Arguments:
            key             The encryption key - a string that must be
                            either 16, 24 or 32 bytes long. Longer keys
                            are more secure.
            in_filename     Path to the file to be encrypted.
            out_dir         Path to the folder where the encrypted file will be
                            generated.
            out_filename    The name for the encrypted file to be generated.
                            If no filename is supplied, the encrypted file name
                            will be the original plus the `.enc` suffix.
            chunksize       Sets the size of the chunk which the function
                            uses to read and encrypt the file. Larger chunk
                            sizes can be faster for some files and machines.
                            chunksize must be divisible by 16.
    """
    if not out_filename:
        out_filename = os.path.basename(in_filename) + '.enc'

    iv = os.urandom(16)
    encryptor = AES.new(key, AES.MODE_CBC, iv)
    filesize = os.path.getsize(in_filename)

    with open(in_filename, 'rb') as infile:
        with open(out_dir + out_filename, 'wb') as outfile:
            outfile.write(struct.pack('<Q', filesize))
            outfile.write(iv)

            while True:
                chunk = infile.read(chunksize)
                if len(chunk) == 0:
                    break
                elif len(chunk) % 16 != 0:
                    chunk += ' '.encode("UTF-8") * (16 - len(chunk) % 16)

                outfile.write(encryptor.encrypt(chunk))

def encrypt_string(text_to_encrypt, public_key_file):
    """ Encrypt the supplied string using our public key.

        Arguments:
            text_to_encrypt     The plain text to encrypt
            public_key_file     The public key to be used for encryption

        Return:
            encrypted_text     The encrypted text using the public key
    """

    with open(public_key_file, 'r') as pub_file:
        pub_key = RSA.importKey(pub_file.read())

    cipher = PKCS1_OAEP.new(pub_key)
    encrypted_text = cipher.encrypt(text_to_encrypt)
    return encrypted_text


def main():
    parser_description = "Encrypt a directory"
    parser = argparse.ArgumentParser(description=parser_description)
    parser.add_argument("--source",
                        help="Path to the directory with the files to encrypt",
                        required=True)
    destination_message = "Path to the directory where the encrypted files \
will be exported. If none provided, the same as the source will be selected \
and the original files will be removed."
    parser.add_argument("--destination", help=destination_message)
    parser.add_argument("--public-key",
                        help="Path to the public key", default="./key.public")
    args = parser.parse_args()

    # Check to see if there is actually a public key file
    if not os.path.isfile(args.public_key):
        print ("Public key not found: " + args.public_key)
        sys.exit(1)

    # If no destination was provided, then the destination is the source
    if not args.destination:
        args.destination = args.source

    # Generate a random secret that will encrypt the files as AES-256
    aes_secret = os.urandom(32)

    # Recursively encrypt all files and filenames in source folder
    filenames_map = dict()  # Will contain the real - obscured paths combos
    for dirpath, dirnames, filenames in os.walk(args.source):
        for name in filenames:
            filename = os.path.join(dirpath, name)
            # Save the real filepath
            real_filepath = filename.replace(args.source, "")
            # Generate a salted file path
            salted_path = (str(os.urandom(16)) + real_filepath).encode("UTF-8")
            # Create a unique obscured filepath by hashing the salted filpath
            unique_name = hashlib.sha512(salted_path).hexdigest()
            # Save it to the filenames map along with the original filepath
            filenames_map[unique_name] = real_filepath
            # Encrypt the clear text file and give it an obscured name
            encrypt_file(aes_secret, filename, args.destination, unique_name)
            # If we are encrypting in the same folder as the clear text files
            # then remove the original unencrypted files
            if args.source == args.destination:
                if os.path.exists(filename):
                    os.remove(filename)

    # Save and encrypt the mapping between real and obscured filepaths
    json_map_name = "filenames_map"
    json_tmp_path = "/tmp/" + json_map_name
    # Save the mapping as a temporary cleartext json file
    with open(json_tmp_path, "w") as cleartext_json:
        json.dump(filenames_map, cleartext_json)
    # Encrypt the cleartext json file
    encrypt_file(aes_secret, json_tmp_path, args.destination, json_map_name)
    # Remove the temporary cleartext file
    if os.path.exists(json_tmp_path):
        os.remove(json_tmp_path)
    # Encrypt and save our AES secret using the public key for the holder of
    # the private key to be able to decrypt the files.
    with open(args.destination + "aes_secret", "wb") as key_file:
        key_file.write(encrypt_string(aes_secret, args.public_key))


if __name__ == "__main__":
    main()