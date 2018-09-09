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
            vil_ua, 'tofu-vilmibm', 'item', dict(
                name='a block of tofu',
                description='squishy and cubic'))
        self.tallgeese = GameObject.create_scripted_object(
            zechs_ua, 'tallgeese-zechs', 'item', dict(
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
        self.tallgeese.set_perm('carry', 'owner')
        assert not self.vil.can_carry(self.tallgeese)

    def test_set_perm_fails_for_garbage(self):
        with self.assertRaisesRegex(ValueError, 'Invalid permission fart'):
            self.tofu.set_perm('fart', 'owner')

        with self.assertRaisesRegex(ValueError, 'Invalid permission mode fart'):
            self.tofu.set_perm('carry', 'fart')

    def test_bulk_set_perm(self):
        self.tofu.set_perms(
            carry='owner',
            execute='owner',
            read='owner',
            write='owner')
        assert not self.zechs.can_carry(self.tofu)
        assert not self.zechs.can_read(self.tofu)
        assert not self.zechs.can_write(self.tofu)
        assert not self.zechs.can_execute(self.tofu)
