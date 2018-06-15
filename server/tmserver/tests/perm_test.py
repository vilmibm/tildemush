from ..models import UserAccount, GameObject, Permission
from .tm_test_case import TildemushTestCase

class PermissionTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        vil_ua = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux')
        zechs_ua = UserAccount.create(
            username='zechs',
            password='foobarbazquux')
        self.vil = vil_ua.player_obj
        self.zechs = zechs_ua.player_obj
        self.tofu = GameObject.create_scripted_object(
            'item', vil_ua, 'tofu-vilmibm', dict(
                name='a block of tofu',
                description='squishy and cubic'))
        self.tallgeese = GameObject.create_scripted_object(
            'item', zechs_ua, 'tallgeese-zechs', dict(
                name='a large mobile suit',
                description='tall and fast'))


    def test_default_perms(self):
        assert self.vil.can_carry(self.tofu)
        assert self.vil.can_read(self.tofu)
        assert self.vil.can_write(self.tofu)
        assert self.vil.can_execute(self.tofu)

        assert not self.zechs.can_write(self.tofu)
        assert self.zechs.can_read(self.tofu)
        assert self.zechs.can_carry(self.tofu)
        assert self.zechs.can_execute(self.tofu)

    def test_can_modify_perms(self):
        assert self.vil.can_carry(self.tallgeese)
        self.tallgeese.perms.carry = Permission.OWNER
        self.tallgeese.perms.save()
        assert not self.vil.can_carry(self.tallgeese)
