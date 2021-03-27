FILES_TO_ENCRYPT=$(shell cat .gitencrypt)
FILES_ENCRYPTED=$(FILES_TO_ENCRYPT:=.secret)
GPG=gpg

encrypt: $(FILES_ENCRYPTED)
.PHONY: encrypt

decrypt: $(FILES_TO_ENCRYPT)
.PHONY: decrypt

$(FILES_TO_ENCRYPT):
	@$(GPG) --decrypt --batch -o $@ $(@:=.secret)

%.secret: %
	@$(GPG) --encrypt --default-recipient-self --armor -o $@ $^
