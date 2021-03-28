FILES_TO_ENCRYPT=$(shell cat .gitencrypt)
FILES_ENCRYPTED=$(FILES_TO_ENCRYPT:=.secret)
GPG=gpg

encrypt: $(FILES_ENCRYPTED)
.PHONY: encrypt

decrypt: $(FILES_TO_ENCRYPT)
.PHONY: decrypt

%:: %.secret
	@$(GPG) --decrypt -o $@ $(@:=.secret)
	@touch -r $? $@ # to be no newer than the encrypted one

%.secret:: %
	@$(GPG) --encrypt --default-recipient-self --armor -o $@ $^
