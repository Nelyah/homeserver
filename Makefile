FILES_TO_ENCRYPT=$(shell cat .gitencrypt)
FILES_ENCRYPTED=$(FILES_TO_ENCRYPT:=.secret)
GPG=gpg

help:
	@printf "Usage:\n\n\
	make encrypt\t\tEncrypt files listed in .gitencrypt file\n\
	make decrypt\t\tDecrypt the .secret files of those listed in .gitencrypt file\n\
	make clean\t\tRemove non-encrypted files\n"
.PHONY: help

encrypt: $(FILES_ENCRYPTED)
.PHONY: encrypt

decrypt: $(FILES_TO_ENCRYPT)
.PHONY: decrypt

%:: %.secret
	@$(GPG) --decrypt -o $@ $<
	@touch -r $? $@ # to be no newer than the encrypted one

%.secret:: %
	@$(GPG) --encrypt --yes --default-recipient-self --armor -o $@ $^

clean:
	@rm -f $(FILES_TO_ENCRYPT)
.PHONY: clean
