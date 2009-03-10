ME = $(shell pwd | sed -e 's/\//\\\//g')

install:
	@echo "Installing .desktop file in "$(HOME)"/.local/share/applications/facebook.desktop"
	@cat facebook.desktop | sed -e "s/Exec=/Exec=$(ME)\//g" -e 's/Icon=facebook/Icon=$(ME)\/icons\/hicolor\/48x48\/apps\/facebook.png/g' > $(HOME)/.local/share/applications/facebook.desktop

uninstall:
	@echo "Removing .desktop file from "$(HOME)"/.local/share/applications/facebook.desktop"
	@rm -f $(HOME)/.local/share/applications/facebook.desktop
