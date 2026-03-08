
class UserObject:
    def __init__(
            self,
            user: dict
    ) -> None:
        self.user = user
        self.profile = self.user.get('profile')
        self.user_id = self.profile.get('id')
        self.email = self.profile.get('emailAddress')
        self.name = self.get_name()
        self.verified_teacher = self.profile.get('verifiedTeacher', False)

    def get_name(self) -> str:
        if 'fullName' in self.profile.get('name'):
            name = self.profile['name']['fullName']
        elif 'familyName' and 'givenName' in self.profile.get('name'):
            name = f'{self.profile["name"]["givenName"]} {self.profile["familyName"]}'
        elif 'givenName' in self.profile.get('name'):
            name = self.profile['name']['givenName']
        else:
            name = self.email
        return name
