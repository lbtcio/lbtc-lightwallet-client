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

    def keyPressEvent(self, event):
        if event.key() in [ Qt.Key_Space ] :
            item = self.currentItem()
            if (item.checkState(0) == Qt.Checked) :
                item.setCheckState(0, Qt.Unchecked)
            else :
                item.setCheckState(0, Qt.Checked)
            self.on_itemclicked(item, self.currentColumn())
        else :
            super(DelegateList, self).keyPressEvent(event)

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
        #self.filter_status = 0
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
            if not len(self.parent.wallet.get_address_history(each)) :
                continue;
            try :
                ret_ls = self.parent.network.synchronous_get(('blockchain.address.listvoteddelegates', [each]))
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
        addr = item.text(3)
        
        if (item.checkState(0) == Qt.Checked) :
            if not (addr in self.selected_list) :
                self.selected_list.append(addr)
        elif (item.checkState(0) == Qt.Unchecked) :
            if addr in self.selected_list :
                self.selected_list.remove(addr)
        self.print_error("selected :", self.selected_list)

    def keyPressEvent(self, event):
        if event.key() in [ Qt.Key_Space ] :
            item = self.currentItem()
            if (item.checkState(0) == Qt.Checked) :
                item.setCheckState(0, Qt.Unchecked)
            else :
                item.setCheckState(0, Qt.Checked)
            self.on_itemclicked(item, self.currentColumn())
        else :
            super(MyVoteList, self).keyPressEvent(event)

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
        MyTreeWidget.__init__(self, parent, self.create_menu, [_('VoteName'), _('VoteAddress'), _('MyName'), _('MyAddress')], 1)
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

#################################### CommitteeList #########################################
class CommitteeList(MyTreeWidget, PrintError):
    filter_columns = [0, 1, 2, 3]  # space, id, name, address

    def __init__(self, parent):
        MyTreeWidget.__init__(self, parent, self.create_menu, [_(' '), _('Name'), _('Address'), _("URL")], 1)
        self.parent = parent
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.itemClicked.connect(self.on_itemclicked)
        self.committee_list = []
        self.recently_committees = []
        self.addr_e = QLineEdit(self)
        self.addr_e.setText('')
        self.selected_list = []
        self.vote_button = EnterButton(_("Vote"), self.toggle_vote)
        self.cancelvote_button = EnterButton(_("CancelVote"), self.toggle_cancelvote)
        self.refresh_button = EnterButton(_("AllCommittee"), self.toggle_refresh)
        self.myvote_button = EnterButton(_("MyVoteCommittee"), self.toggle_vote_committee)
        self.selected_name = ''
        self.voter_ls = []
        self.status = 0 # default all committee list  0 -- all committee; 1 -- my vote committee
        self.update()

    def get_list_header(self):
        #return QLabel(_("Filter:")), self.filter_button, QLabel(_("Address:")), self.addr_e, self.vote_button
        return QLabel(_("Fee Address:")), self.addr_e, self.vote_button, self.cancelvote_button, self.refresh_button, self.myvote_button
        
    def toggle_vote(self):
    
        if not self.addr_e.text().strip() :
            self.parent.show_error(_('please input address.'))
            return
            
        if not self.parent.wallet.is_mine(self.addr_e.text()):
            self.parent.show_message(self.addr_e.text() + _('is not your own address!'))
            return
            
        # only vote once
        vote_ls = self.parent.get_voter_committee(self.addr_e.text().strip())
        if(vote_ls):
            self.parent.show_message(_('You have voted to ') + vote_ls[0].get('name'))
            return
            
        op_code = 0xc4
        self.parent.do_vote(self.addr_e.text(), op_code, self.selected_list)
        self.selected_list = []
        self.addr_e.setText('')
        self.update()
        
    def toggle_cancelvote(self):
    
        if not self.addr_e.text().strip() :
            self.parent.show_error(_('please input address.'))
            return
            
        if not self.parent.wallet.is_mine(self.addr_e.text()):
            self.parent.show_message(self.addr_e.text() + _('is not your own address!'))
            return

        vote_ls = self.parent.get_committee_voter(self.selected_name)
        voted = False
        for each in vote_ls:
            if(self.addr_e.text() and each.get('address') == self.addr_e.text()):
                voted = True
                break
        if self.addr_e.text() and not voted:     
            self.parent.show_message(_('You have not voted to ') + self.selected_name)
            return
            
        op_code = 0xc5
        self.parent.do_vote(self.addr_e.text(), op_code, self.selected_list)
        self.selected_list = []
        self.addr_e.setText('')
        self.update()

    def toggle_refresh(self):
        self.committee_list = []
        self.selected_list = []
        self.selected_name = ''
        self.status = 0
        try :
            self.committee_list = self.parent.network.synchronous_get(('blockchain.address.getcommittee', ['']))
        except BaseException as e:
            self.print_error("error: " + str(e))
            self.committee_list = []
        self.update()

    def toggle_vote_committee(self):
        self.voter_ls = []
        self.addr_e.setText('')
        self.status = 1
        addr_ls = self.parent.wallet.get_addresses()
        ret_ls = []
        for each in addr_ls :
            # ignore non-history address
            if not len(self.parent.wallet.get_address_history(each)) :
                continue;
            ret_ls = self.parent.get_voter_committee(each)
            for item in ret_ls :
                #self.print_error("error: " + item.get('voter'))
                self.voter_ls.append(item)
            
        self.update()

    def load_committees(self):
        self.recently_committees = self.parent.wallet.storage.get('recently_committees', [])
        self.update()
        
    def add_selected(self, name, addr):
        self.selected_list.clear()
        self.selected_name = name
        self.selected_list.append(addr)
        
    def on_itemclicked(self, item, column):
        name = item.text(1)
        addr = item.text(2)
        
        if (item.checkState(0) == Qt.Checked) :
            self.add_selected(name, addr)
        self.update()
        self.print_error("selected :", self.selected_list)

    def keyPressEvent(self, event):
        if event.key() in [ Qt.Key_Space ] :
            item = self.currentItem()
            if (item.checkState(0) == Qt.Checked) :
                item.setCheckState(0, Qt.Unchecked)
            else :
                item.setCheckState(0, Qt.Checked)
            self.on_itemclicked(item, self.currentColumn())
        else :
            super(CommitteeList, self).keyPressEvent(event)

    def on_permit_edit(self, item, column):
        # openalias items shouldn't be editable
        return False

    def on_edited(self, item, column, prior):
        pass

    def create_menu(self, position):
        item = self.currentItem()
        if not item:
            return
        column = self.currentColumn()
        if column is 0:
            column_title = ""
            column_data = ''
        else:
            column_title = self.headerItem().text(column)
            column_data = item.text(column)
    
        menu = QMenu()
        #selected = self.selectedItems()
        item = self.itemAt(position)
        url = item.text(3)
        if (column == 3) and url:
            menu.addAction(_("View on explorer"), lambda: webbrowser.open(url))
        if column:
            menu.addAction(_("Copy ") + column_title, lambda: self.parent.app.clipboard().setText(column_data))
        #run_hook('create_contact_menu', menu, selected)
        menu.exec_(self.viewport().mapToGlobal(position))

    def fetch_committee(self):
        try :
            self.committee_list = self.parent.network.synchronous_get(('blockchain.address.getcommittee', ['']))
        except BaseException as e:
            self.print_error("error: " + str(e))
            
    def on_update(self):
        #self.out_vote = self.parent.get_out_vote()
        #self.print_error("out_vote : ", self.out_vote)
        item = self.currentItem()
        current_key = item.data(2, Qt.UserRole) if item else None
        self.clear()
        self.print_error("committee :", self.committee_list)
        #self.print_error("selected :", self.selected_list)
        #self.print_error("filter :", self.filter_status)
        if self.status == 1 :
            tmp_ls = self.voter_ls
        else:
            tmp_ls = self.committee_list
            
        if len(tmp_ls) :
            for each in tmp_ls:
                item = QTreeWidgetItem(['', each.get('name'), each.get('address'), each.get('url')])
                #item.setData(3, Qt.UserRole, each.get('address'))
                if(self.selected_list and self.selected_list[0] == each.get('address')):
                    item.setCheckState(0, Qt.Checked)
                else:
                    item.setCheckState(0, Qt.Unchecked)
                self.addTopLevelItem(item)
                if each.get('address') == current_key:
                    self.setCurrentItem(item)
        self.print_error("selected :", self.selected_list)
        #run_hook('update_contacts_tab', self)

#################################### BillList #########################################
from electrum.util import format_time
import json,time

class BillList(MyTreeWidget, PrintError):
    filter_columns = [1, 2, 3, 4]  # title, detail, url, endtime, options

    def __init__(self, parent):
        MyTreeWidget.__init__(self, parent, self.create_menu, [_(' '), _('Title'), _('Detail'), _('URL'), _('EndTime'), _('Options')], 1)
        self.parent = parent
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.itemClicked.connect(self.on_itemclicked)
        self.bill_list = []
        self.recently_bills = []
        self.addr_e = QLineEdit(self)
        self.addr_e.setText('')
        self.selected_list = []
        self.voter_ls = []
        self.vote_button = EnterButton(_("Vote"), self.toggle_vote)
        #self.cancelvote_button = EnterButton(_("CancelVote"), self.toggle_cancelvote)
        self.refresh_button = EnterButton(_("AllBill"), self.toggle_refresh)
        self.myvote_button = EnterButton(_("MyVoteBill"), self.toggle_myvote_bill)
        self.selected_name = ''
        self.filter_status = 0
        self.status = 0 
        
        self.update()

    def get_list_header(self):
        #return QLabel(_("Filter:")), self.filter_button, QLabel(_("Address:")), self.addr_e, self.vote_button
        return QLabel(_("Fee Address:")), self.addr_e, self.vote_button, self.refresh_button, self.myvote_button
        
    def toggle_vote(self):
        if self.selected_list and (self.selected_list[0].get('endtime') <= str(int(time.time()))):
            self.parent.show_message(_('not vote to expired bill!'))
            return
            
        if not self.addr_e.text().strip() :
            self.parent.show_error(_('please input address.'))
            return
            
        if not self.parent.wallet.is_mine(self.addr_e.text()):
            self.parent.show_message(self.addr_e.text() + _('is not your own address!'))
            return
            
        if self.selected_list:
            vote_ls = self.parent.get_voter_bill(self.addr_e.text().strip())
            for each in vote_ls:
                if(each.get('id') == self.selected_list[0].get('id')):
                    self.parent.show_message(_('You have voted to ') + self.selected_list[0].get('title'))
                    return
            
        op_code = 0xc7 # vote for bill
        self.parent.do_bill_vote(self.addr_e.text(), op_code, self.selected_list)
        self.selected_list = []
        self.addr_e.setText('')
        self.update()
        
    def toggle_cancelvote(self):
        op_code = 0xff
        self.parent.do_bill_vote(self.addr_e.text(), op_code, self.selected_list)
        self.selected_list = []
        self.addr_e.setText('')
        self.update()

    def toggle_refresh(self):
        self.bill_list = []
        self.selected_list = []
        self.voter_ls = []
        self.selected_name = ''
        self.status = 0
        try :
            self.bill_list = self.parent.network.synchronous_get(('blockchain.address.getbill', ['']))
        except BaseException as e:
            self.print_error("error: " + str(e))
            self.bill_list = []
        self.update()

    def toggle_myvote_bill(self):
        if not self.bill_list:
            self.fetch_bill()
        self.selected_list = []
        self.voter_ls = []
        self.addr_e.setText('')
        self.status = 1
        addr_ls = self.parent.wallet.get_addresses()
        ret_ls = []
        for each in addr_ls :
            # ignore non-history address
            if not len(self.parent.wallet.get_address_history(each)) :
                continue;
            ret_ls = self.parent.get_voter_bill(each)
            for item in ret_ls :
                #self.print_error("error: " + item.get('voter'))
                for bill in self.bill_list:
                    if item.get('id') == bill.get('id'):
                        self.print_error("item: ", item)
                        bill['index'] = bill['options'][item['index']]['option']
                        self.voter_ls.append(bill)
        self.update()

    def load_bills(self):
        self.recently_bills = self.parent.wallet.storage.get('recently_bills', [])
        self.update()
        
    def on_itemclicked(self, item, column):
        title_hash = item.text(6)
        title = item.text(1)
        endtime = item.text(7)
        if (item.checkState(0) == Qt.Checked) :
            self.selected_list.clear()
            self.selected_list.append({'id':title_hash, 'title':title, 'index':self.filter_status, 'endtime':endtime})
        self.update()
        self.print_error("selected :", self.selected_list)

    def keyPressEvent(self, event):
        if event.key() in [ Qt.Key_Space ] :
            item = self.currentItem()
            if (item.checkState(0) == Qt.Checked) :
                item.setCheckState(0, Qt.Unchecked)
            else :
                item.setCheckState(0, Qt.Checked)
            self.on_itemclicked(item, self.currentColumn())
        else :
            super(BillList, self).keyPressEvent(event)

    def on_permit_edit(self, item, column):
        # openalias items shouldn't be editable
        return False

    def on_edited(self, item, column, prior):
        pass

    def create_menu(self, position):
        item = self.currentItem()
        if not item:
            return
        column = self.currentColumn()
        if column is 0:
            column_title = ""
            column_data = ''
        else:
            column_title = self.headerItem().text(column)
            column_data = item.text(column)
    
        menu = QMenu()
        #selected = self.selectedItems()
        item = self.itemAt(position)
        url = item.text(3)
        if (column == 3) and url:
            menu.addAction(_("View on explorer"), lambda: webbrowser.open(url))
        if column:
            menu.addAction(_("Copy ") + column_title, lambda: self.parent.app.clipboard().setText(column_data))
        #run_hook('create_contact_menu', menu, selected)
        menu.exec_(self.viewport().mapToGlobal(position))

    def fetch_bill(self):
        try :
            self.bill_list = self.parent.network.synchronous_get(('blockchain.address.getbill', ['']))
        except BaseException as e:
            self.print_error("error: " + str(e))

    def toggle_filter(self, state):
        if state == self.filter_status:
            return
        self.filter_status = state
        if(self.selected_list):
            self.selected_list[0]['index'] = state
        self.print_error("filter :", self.filter_status)
        self.print_error("toggle_filter selected :", self.selected_list)
        #self.update()

    def on_update(self):
        #self.out_vote = self.parent.get_out_vote()
        #self.print_error("out_vote : ", self.out_vote)
        item = self.currentItem()
        current_key = item.data(6, Qt.UserRole) if item else None
        self.clear()
        #self.print_error("bill :", self.bill_list)
        self.print_error("status :", self.status)
        self.print_error("voted :", self.voter_ls)
        if self.status == 1 :
            tmp_ls = self.voter_ls
        else:
            tmp_ls = self.bill_list
        if len(tmp_ls) :
            for each in tmp_ls:
                item = QTreeWidgetItem(self)
                if(self.selected_list and each.get('id') == self.selected_list[0].get('id')):
                    item.setCheckState(0, Qt.Checked)
                else:
                    item.setCheckState(0, Qt.Unchecked)
                item.setText(1, each.get('title'))
                item.setText(2, each.get('detail'))
                item.setText(3, each.get('url'))
                item.setText(4, format_time(each.get('endtime')))
                filter_button = QComboBox(self)
                filter_button.currentIndexChanged.connect(self.toggle_filter)
                #self.connect(filter_button, QtCore.SIGNAL("currentIndexChanged(int)"), self.toggle_filter)
                for option in each.get('options'):
                    filter_button.addItem(option.get('option'))
                if(self.selected_list and each.get('id') == self.selected_list[0].get('id')):
                    filter_button.setCurrentIndex(self.selected_list[0].get('index'))
                #if hasattr(each, 'index'): # myvote bill
                    #filter_button.setCurrentIndex(each.get('index'))
                if (self.status == 1):
                    self.print_error("each :", each)
                    if 'index' in each: # myvote bill
                        item.setText(5, each.get('index'))
                else:
                    self.setItemWidget(item, 5, filter_button)
                item.setText(6, each.get('id'))
                item.setText(7, str(each.get('endtime')))
                if(each.get('endtime') <= (int(time.time()))):
                    for i in range(8):
                        item.setBackground(i, QColor('red'))
                #item = QTreeWidgetItem([each.get('title'), each.get('detail'), each.get('url'), format_time(each.get('endtime')), json.dumps(each.get('options'), indent=4)])
                self.addTopLevelItem(item)
                if each.get('id') == current_key:
                    self.setCurrentItem(item)
        self.print_error("selected :", self.selected_list)
        #run_hook('update_contacts_tab', self)


