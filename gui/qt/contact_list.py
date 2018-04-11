#!/usr/bin/env python
#
# Electrum - lightweight Bitcoin client
# Copyright (C) 2015 Thomas Voegtlin
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import webbrowser

from electrum.i18n import _
from electrum.bitcoin import is_address
from electrum.util import block_explorer_URL
from electrum.plugins import run_hook
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import (
    QComboBox, QLabel, QAbstractItemView, 
    QLineEdit, QFileDialog, QMenu, QTreeWidgetItem)
from .util import MyTreeWidget
from .util import EnterButton

class ContactList(MyTreeWidget):
    filter_columns = [0, 1]  # Key, Value

    def __init__(self, parent):
        MyTreeWidget.__init__(self, parent, self.create_menu, [_('Name'), _('Address')], 0, [0])
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)

    def on_permit_edit(self, item, column):
        # openalias items shouldn't be editable
        return item.text(1) != "openalias"

    def on_edited(self, item, column, prior):
        if column == 0:  # Remove old contact if renamed
            self.parent.contacts.pop(prior)
        self.parent.set_contact(item.text(0), item.text(1))

    def import_contacts(self):
        wallet_folder = self.parent.get_wallet_folder()
        filename, __ = QFileDialog.getOpenFileName(self.parent, "Select your wallet file", wallet_folder)
        if not filename:
            return
        self.parent.contacts.import_file(filename)
        self.on_update()

    def create_menu(self, position):
        menu = QMenu()
        selected = self.selectedItems()
        if not selected:
            menu.addAction(_("New contact"), lambda: self.parent.new_contact_dialog())
            menu.addAction(_("Import file"), lambda: self.import_contacts())
        else:
            names = [item.text(0) for item in selected]
            keys = [item.text(1) for item in selected]
            column = self.currentColumn()
            column_title = self.headerItem().text(column)
            column_data = '\n'.join([item.text(column) for item in selected])
            menu.addAction(_("Copy %s")%column_title, lambda: self.parent.app.clipboard().setText(column_data))
            if column in self.editable_columns:
                item = self.currentItem()
                menu.addAction(_("Edit %s")%column_title, lambda: self.editItem(item, column))
            menu.addAction(_("Pay to"), lambda: self.parent.payto_contacts(keys))
            menu.addAction(_("Delete"), lambda: self.parent.delete_contacts(keys))
            URLs = [block_explorer_URL(self.config, 'addr', key) for key in filter(is_address, keys)]
            if URLs:
                menu.addAction(_("View on block explorer"), lambda: map(webbrowser.open, URLs))

        run_hook('create_contact_menu', menu, selected)
        menu.exec_(self.viewport().mapToGlobal(position))

    def on_update(self):
        item = self.currentItem()
        current_key = item.data(0, Qt.UserRole) if item else None
        self.clear()
        for key in sorted(self.parent.contacts.keys()):
            _type, name = self.parent.contacts[key]
            item = QTreeWidgetItem([name, key])
            item.setData(0, Qt.UserRole, key)
            self.addTopLevelItem(item)
            if key == current_key:
                self.setCurrentItem(item)
        run_hook('update_contacts_tab', self)

#################################### DelegateList #########################################
from electrum.util import PrintError
class DelegateList(MyTreeWidget, PrintError):
    filter_columns = [0, 1, 2]  # space, id, name, address

    def __init__(self, parent):
        MyTreeWidget.__init__(self, parent, self.create_menu, [_(' '), _('Name'), _('Address')], 1)
        self.parent = parent
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.itemClicked.connect(self.on_itemclicked)
        self.delegate_list = []
        self.recently_delegates = []
        self.addr_e = QLineEdit(self)
        self.addr_e.setText('')
        self.selected_list = []
        self.vote_button = EnterButton(_("Vote"), self.toggle_vote)
        self.refresh_button = EnterButton(_("Refresh"), self.toggle_refresh)
        self.store_button = EnterButton(_("StoreDelegates"), self.toggle_store_delegate)
        #self.filter_button = QComboBox(self)
        #for t in [_('All'), _('Voted'), _('Unvoted'), _('Selected')]:
            #self.filter_button.addItem(t)
        #self.filter_button.setCurrentIndex(0)
        #self.filter_button.currentIndexChanged.connect(self.toggle_filter)
        #try :
            #self.delegate_list = self.parent.network.synchronous_get(('blockchain.address.getwitness', ['']))
        #except BaseException as e:
            #self.print_error("error: " + str(e))
            #self.delegate_list = []

        self.update()

    def get_list_header(self):
        #return QLabel(_("Filter:")), self.filter_button, QLabel(_("Address:")), self.addr_e, self.vote_button
        return QLabel(_("Fee Address:")), self.addr_e, self.vote_button, self.refresh_button, self.store_button
        
    def toggle_vote(self):
        op_code = 0xc1
        self.parent.do_vote(self.addr_e.text(), op_code, self.selected_list)
        self.selected_list = []
        self.addr_e.setText('')
        self.update()

    def toggle_refresh(self):
        self.delegate_list = []
        self.selected_list = []
        try :
            self.delegate_list = self.parent.network.synchronous_get(('blockchain.address.getwitness', ['']))
        except BaseException as e:
            self.print_error("error: " + str(e))
            self.delegate_list = []
        self.update()

    def toggle_store_delegate(self):
        self.delegate_list = []
        self.selected_list = []
        if len(self.recently_delegates) :
            self.parent.wallet.storage.put('recently_delegates', self.recently_delegates)
        self.update()

    def load_delegates(self):
        self.recently_delegates = self.parent.wallet.storage.get('recently_delegates', [])
        self.update()

    def on_itemclicked(self, item, column):
        name = item.text(1)
        addr = item.text(2)
        #for each in self.out_vote :
            #if (each == addr) :
                #item.setCheckState(0, Qt.Checked)
                #return
        
        if (item.checkState(0) == Qt.Checked) :
            if not (addr in self.selected_list) :
                self.selected_list.append(addr)

            is_exist = False
            for each in self.recently_delegates :
                if each.get('address') == addr :
                    is_exist = True
            if not is_exist :
                self.recently_delegates.append({'name' : name, 'address' : addr})                
        elif (item.checkState(0) == Qt.Unchecked) :
            if addr in self.selected_list :
                self.selected_list.remove(addr)
            #self.recently_delegates.filter(lambda x: x.get('address') == addr, self.recently_delegates)
            self.recently_delegates = [x for x in self.recently_delegates if not (addr == x.get('address'))]
        self.print_error("selected :", self.selected_list)
        self.print_error("recently_delegates :", self.recently_delegates)

    def on_permit_edit(self, item, column):
        # openalias items shouldn't be editable
        return False

    def on_edited(self, item, column, prior):
        pass

    def create_menu(self, position):
        menu = QMenu()
        selected = self.selectedItems()
        item = self.itemAt(position)
        if selected:
            names = [item.text(1) for item in selected]
            keys = [item.text(2) for item in selected]
            URLs = [block_explorer_URL(self.config, 'addr', key) for key in filter(is_address, keys)]
            #if URLs:
                #menu.addAction(_("View on block explorer"), lambda: map(webbrowser.open, URLs))

        run_hook('create_contact_menu', menu, selected)
        menu.exec_(self.viewport().mapToGlobal(position))

    def fetch_delegate(self):
        try :
            self.delegate_list = self.parent.network.synchronous_get(('blockchain.address.getwitness', ['']))
        except BaseException as e:
            self.print_error("error: " + str(e))
            
    def on_update(self):
        #self.out_vote = self.parent.get_out_vote()
        #self.print_error("out_vote : ", self.out_vote)
        item = self.currentItem()
        current_key = item.data(2, Qt.UserRole) if item else None
        self.clear()
        self.print_error("delegate :", self.delegate_list)
        #self.print_error("selected :", self.selected_list)
        #self.print_error("filter :", self.filter_status)
        if len(self.delegate_list) :
            for each in self.delegate_list:
                item = QTreeWidgetItem(['', each.get('name'), each.get('address')])
                #item.setData(3, Qt.UserRole, each.get('address'))
                item.setCheckState(0, Qt.Unchecked)
                self.addTopLevelItem(item)
                if each.get('address') == current_key:
                    self.setCurrentItem(item)
        elif len(self.recently_delegates) :
            for each in self.recently_delegates:
                item = QTreeWidgetItem(['', each.get('name'), each.get('address')])
                #item.setData(3, Qt.UserRole, each.get('address'))
                item.setCheckState(0, Qt.Checked)
                self.addTopLevelItem(item)
                addr = each.get('address')
                if not (addr in self.selected_list) :
                    self.selected_list.append(addr)
                
                if each.get('address') == current_key:
                    self.setCurrentItem(item)
        self.print_error("selected :", self.selected_list)
        run_hook('update_contacts_tab', self)

#################################### MyVoteList #########################################
class MyVoteList(MyTreeWidget, PrintError):
    filter_columns = [0, 1, 2, 3]  # space, name, address

    def __init__(self, parent):
        MyTreeWidget.__init__(self, parent, self.create_menu, [_(' '), _('Voter'), _('VotedName'), _('VotedAddress')], 1)
        self.parent = parent
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.itemClicked.connect(self.on_itemclicked)
        self.delegate_list = []
        self.vote_ls = []
        self.addr_e = QLineEdit(self)
        self.addr_e.setText('')
        #self.addr_e.textChanged.connect(self.address_changed)        
        self.selected_list = []
        self.vote_button = EnterButton(_("CancelVote"), self.toggle_cancelvote)
        self.refresh_button = EnterButton(_("Refresh"), self.toggle_refresh)
        self.all_button = EnterButton(_("CancelAllShowedVote"), self.toggle_cancelallvote)
        self.filter_status = 0
        #self.filter_button = QComboBox(self)
        #for t in [_('All'), _('Voted'), _('Unvoted'), _('Selected')]:
            #self.filter_button.addItem(t)
        #self.filter_button.setCurrentIndex(0)
        #self.filter_button.currentIndexChanged.connect(self.toggle_filter)
        self.voter_ls = []
        #try :
            #self.delegate_list = self.parent.network.synchronous_get(('blockchain.address.getwitness', ['']))
        #except BaseException as e:
            #self.print_error("error: " + str(e))

    def get_list_header(self):
        #return QLabel(_("Filter:")), self.filter_button, QLabel(_("Address:")), self.addr_e, self.vote_button
        return QLabel(_("Fee Address:")), self.addr_e, self.vote_button, self.refresh_button
        
    def toggle_cancelvote(self):
        op_code = 0xc2
        self.parent.do_vote(self.addr_e.text(), op_code, self.selected_list)
        self.selected_list = []
        self.addr_e.setText('')
        self.update()
        
    def toggle_cancelallvote(self):
        self.selected_list = []
        for item in self.get_leaves(self.invisibleRootItem()):
            if not item.isHidden() :
                self.selected_list.append(item.text(3))

        op_code = 0xc2
        self.parent.do_vote(self.addr_e.text(), op_code, self.selected_list)
        self.addr_e.setText('')
        self.print_error("all cancel selected :", self.selected_list)
        self.selected_list = []
        #self.update()
        
    def address_changed(self, addr):
        if not addr :
            self.toggle_refresh()
            return
            
        if not is_address(addr) :
            return
            
        self.voter_ls = []
        ret_ls = []
        try :
            ret_ls = self.parent.network.synchronous_get(('blockchain.address.listvoteddelegates', [addr]))
        except BaseException as e:
            self.print_error("error: " + str(e))
        for item in ret_ls :
            self.print_error("error: " + item.get('voter'))
            self.voter_ls.append(item)
            
        self.update()

    def print_address(self, addr_ls):
        #addr_ls = self.parent.wallet.get_receiving_addresses()
        index = 0
        for each in addr_ls :
            self.print_error('%d  %s' % (index, each))
            index = index + 1

    def toggle_refresh(self):
        #self.print_address(self.parent.wallet.get_receiving_addresses())
        #self.print_address(self.parent.wallet.get_change_addresses())
        #self.fetch_delegate()
        self.voter_ls = []
        self.addr_e.setText('')
        addr_ls = self.parent.wallet.get_addresses()
        ret_ls = []
        for each in addr_ls :
            # ignore non-history address
            self.print_error("error: ", each, len(self.parent.wallet.get_address_history(each)))
            if not len(self.parent.wallet.get_address_history(each)) :
                continue;
            try :
                ret_ls = self.parent.network.synchronous_get(('blockchain.address.listvoteddelegates', [each]))
                self.print_error("error: ", ret_ls)
            except BaseException as e:
                self.print_error("error: " + str(e))
            for item in ret_ls :
                #self.print_error("error: " + item.get('voter'))
                item['voter'] = each
                self.voter_ls.append(item)
            
        self.update()

    def toggle_filter(self, state):
        if state == self.filter_status:
            return
        self.filter_status = state
        self.update()
        
    def on_itemclicked(self, item, column):
        addr = item.text(3);
        #for each in self.out_vote :
            #if (each == addr) :
                #item.setCheckState(0, Qt.Checked)
                #return
        
        if (item.checkState(0) == Qt.Checked) :
            if not (addr in self.selected_list) :
                self.selected_list.append(addr)
        elif (item.checkState(0) == Qt.Unchecked) :
            if addr in self.selected_list :
                self.selected_list.remove(addr)
        self.print_error("selected :", self.selected_list)

    def on_permit_edit(self, item, column):
        # openalias items shouldn't be editable
        return False

    def on_edited(self, item, column, prior):
        pass

    def create_menu(self, position):
        menu = QMenu()
        selected = self.selectedItems()
        item = self.itemAt(position)
        col = self.currentColumn()
        if len(selected) == 1:
            names = [item.text(2) for item in selected]
            keys = [item.text(3) for item in selected]
            URLs = [block_explorer_URL(self.config, 'addr', key) for key in filter(is_address, keys)]
            #if URLs:
                #menu.addAction(_("View on block explorer"), lambda: map(webbrowser.open, URLs))
            if col : # filter 0 col
                column_title = self.headerItem().text(col)
                copy_text = item.text(col)
                menu.addAction(_("Copy %s")%column_title, lambda: self.parent.app.clipboard().setText(copy_text))
        run_hook('create_contact_menu', menu, selected)
        menu.exec_(self.viewport().mapToGlobal(position))

    def fetch_delegate(self):
        try :
            self.delegate_list = self.parent.network.synchronous_get(('blockchain.address.getwitness', ['']))
        except BaseException as e:
            self.print_error("error: " + str(e))

    def get_address_name(self, addr):
        for each in self.delegate_list :
            if each.get('address') == addr :
                return each.get('name')
        return ''

    def filter_vote_history(self):
        vote_ls = []
        revoke_ls = []
        # devide into two type list
        for each in self.voter_ls :
            if each.get('type') == 'vote' :
                vote_ls.append(each)
            if each.get('type') == 'revoke' :
                revoke_ls.append(each)
        # filter 
        for vote in self.voter_ls :
            for revoke in revoke_ls :
                if ((vote.get('type') == 'vote') 
                    and (vote.get('voter') == revoke.get('voter')) 
                    and (vote.get('delegate') == revoke.get('delegate'))
                    and (vote.get('id') < revoke.get('id'))) :
                    vote['status'] = False
                    #self.print_error("vote :", vote)
        
    def on_update(self):
        #self.filter_vote_history()
        item = self.currentItem()
        current_key = item.data(1, Qt.UserRole) if item else None
        self.clear()
        #self.print_error("delegate :", self.delegate_list)
        self.print_error("selected :", self.selected_list)
        #self.print_error("filter :", self.filter_status)
        for each in self.voter_ls:
                
            addr = each.get('delegate')
            item = QTreeWidgetItem(['', each.get('voter'), each.get('name'), each.get('delegate')])
            #item.setData(3, Qt.UserRole, each.get('address'))
            item.setCheckState(0, Qt.Unchecked)
            self.addTopLevelItem(item)
            if each.get('voter') == current_key:
                self.setCurrentItem(item)
        run_hook('update_contacts_tab', self)

#################################### MyVotedList #########################################

class MyVotedList(MyTreeWidget, PrintError):
    filter_columns = [0, 1, 2, 3]  

    def __init__(self, parent):
        MyTreeWidget.__init__(self, parent, self.create_menu, [_('VoteName'), _('VoterAddress'), _('MyName'), _('MyAddress')], 1)
        self.parent = parent
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.delegate_list = []
        self.refresh_button = EnterButton(_("Refresh"), self.toggle_refresh)
        self.voted_ls = []
        #try :
            #self.delegate_list = self.parent.network.synchronous_get(('blockchain.address.getwitness', ['']))
        #except BaseException as e:
            #self.print_error("error: " + str(e))

    def get_list_header(self):
        return self.refresh_button,
        
    def toggle_refresh(self):
        self.fetch_delegate()
        self.voted_ls = []
        addr_ls = self.parent.wallet.get_addresses()
        ret_ls = []
        for each in addr_ls :
            # ignore non-history address
            if not len(self.parent.wallet.get_address_history(each)) :
                continue;
            name = self.get_address_name(each)
            if not name : # not registered miner
                continue
            try :
                ret_ls = self.parent.network.synchronous_get(('blockchain.address.listreceivedvotes', [name]))
            except BaseException as e:
                self.print_error("error: " + str(e))
            for item in ret_ls :
                #self.print_error("error: " + item.get('voter'))
                self.voted_ls.append({'voter':each, 'voted':item})
            
        self.update()
        
    def on_permit_edit(self, item, column):
        # openalias items shouldn't be editable
        return False

    def on_edited(self, item, column, prior):
        pass

    def create_menu(self, position):
        menu = QMenu()
        selected = self.selectedItems()
        item = self.itemAt(position)
        if selected:
            names = [item.text(2) for item in selected]
            keys = [item.text(3) for item in selected]
            URLs = [block_explorer_URL(self.config, 'addr', key) for key in filter(is_address, keys)]
            #if URLs:
                #menu.addAction(_("View on block explorer"), lambda: map(webbrowser.open, URLs))

        run_hook('create_contact_menu', menu, selected)
        menu.exec_(self.viewport().mapToGlobal(position))

    def get_address_name(self, addr):
        for each in self.delegate_list :
            if each.get('address') == addr :
                return each.get('name')
        return ''

    def fetch_delegate(self):
        try :
            self.delegate_list = self.parent.network.synchronous_get(('blockchain.address.getwitness', ['']))
        except BaseException as e:
            self.print_error("error: " + str(e))

    def on_update(self):
        item = self.currentItem()
        current_key = item.data(3, Qt.UserRole) if item else None
        self.clear()
        self.print_error("delegate :", self.delegate_list)
        #self.print_error("selected :", self.selected_list)
        #self.print_error("filter :", self.filter_status)
        for each in self.voted_ls:
            voter = each.get('voter')
            voted = each.get('voted')
            item = QTreeWidgetItem([self.get_address_name(voted), voted, self.get_address_name(voter), voter])
            #item.setData(3, Qt.UserRole, each.get('address'))
            #item.setCheckState(0, Qt.Unchecked)
            self.addTopLevelItem(item)
            if each.get('voter') == current_key:
                self.setCurrentItem(item)
        run_hook('update_contacts_tab', self)

