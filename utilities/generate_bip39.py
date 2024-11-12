from mnemonic import Mnemonic

def main():
    mnemo = Mnemonic("english")
    print(mnemo.generate(strength=128))

if __name__ == "__main__":
    main()
